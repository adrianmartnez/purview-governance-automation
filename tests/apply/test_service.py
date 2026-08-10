"""Unit tests for execute_governance_plan safety and write classification."""

from __future__ import annotations

import httpx
import pytest

from purview_governance.apply import (
    ApplyValidationError,
    ExecutionMode,
    execute_governance_plan,
)
from purview_governance.auth import PurviewAuthorizationProvider
from purview_governance.plan import build_governance_plan
from purview_governance.remote_state.models import build_remote_state
from purview_governance.scanning import PurviewScanningClient
from tests.auth.fakes import FakeTokenCredential
from tests.contract.client_helpers import make_loopback_client
from tests.contract.server import AUTH_SENTINEL, start_contract_server
from tests.plan.helpers import create_config, empty_remote, remote_ds


def _create_plan():
    return build_governance_plan(create_config(), empty_remote())


def test_invalid_mode_raises_before_result() -> None:
    plan = _create_plan()
    with (
        start_contract_server(list_mode="empty") as server,
        make_loopback_client(server.base_url) as client,
        pytest.raises(ApplyValidationError) as exc,
    ):
        execute_governance_plan(plan, client, mode="apply")  # type: ignore[arg-type]
    assert exc.value.code == "apply.invalid_mode"
    assert server.state.recordings == []


def test_blocked_zero_network() -> None:
    remote = build_remote_state((remote_ds(creation_type="AutoNative"),), ())
    plan = build_governance_plan(create_config(), remote)
    with (
        start_contract_server(list_mode="empty") as server,
        make_loopback_client(server.base_url) as client,
    ):
        result = execute_governance_plan(plan, client)
    assert result.status == "blocked"
    assert result.execution_target_context_identity is None
    assert result.writes_attempted == 0
    assert server.state.recordings == []


def test_wrong_target_zero_network() -> None:
    plan = _create_plan()
    with (
        start_contract_server(list_mode="empty") as server,
        make_loopback_client(
            server.base_url,
            logical_target_endpoint="https://other.purview.azure.com",
        ) as client,
    ):
        result = execute_governance_plan(plan, client)
    assert result.status == "wrong-target"
    assert result.execution_target_context_identity is not None
    assert result.execution_target_context_identity != result.planned_target_context_identity
    assert result.observed_remote_state_identity is None
    assert server.state.recordings == []


def test_dry_run_ready_zero_put() -> None:
    plan = _create_plan()
    with (
        start_contract_server(list_mode="empty") as server,
        make_loopback_client(server.base_url) as client,
    ):
        result = execute_governance_plan(plan, client)
    assert result.status == "dry-run-ready"
    assert result.writes_performed == 0
    assert result.writes_attempted == 0
    assert all(op.status == "not-run" for op in result.operations)
    assert not any(r.method == "PUT" for r in server.state.recordings)
    assert any(r.method == "GET" for r in server.state.recordings)


def test_apply_create_one_put() -> None:
    plan = _create_plan()
    expected_body = {
        "kind": "AzureStorage",
        "properties": {
            "collection": {"referenceName": "root"},
            "endpoint": "https://example.blob.core.windows.net/",
        },
    }
    with (
        start_contract_server(
            list_mode="empty",
            put_mode="created",
            put_expected_body=expected_body,
        ) as server,
        make_loopback_client(server.base_url) as client,
    ):
        result = execute_governance_plan(plan, client, mode=ExecutionMode.APPLY)
    assert result.status == "applied"
    assert result.writes_performed == 1
    assert result.writes_attempted == 1
    puts = [r for r in server.state.recordings if r.method == "PUT"]
    assert len(puts) == 1
    assert puts[0].path == "/scan/datasources/example-source"
    assert puts[0].json_body == expected_body


def test_stale_get_zero_put() -> None:
    plan = _create_plan()
    with (
        start_contract_server(list_mode="one_page", get_mode="success") as server,
        make_loopback_client(server.base_url) as client,
    ):
        result = execute_governance_plan(plan, client, mode=ExecutionMode.APPLY)
    assert result.status == "stale"
    assert result.writes_attempted == 0
    assert not any(r.method == "PUT" for r in server.state.recordings)


def test_first_put_client_error_write_failed() -> None:
    plan = _create_plan()
    with (
        start_contract_server(list_mode="empty", put_mode="client_error") as server,
        make_loopback_client(server.base_url) as client,
    ):
        result = execute_governance_plan(plan, client, mode=ExecutionMode.APPLY)
    assert result.status == "write-failed"
    assert result.writes_performed == 0
    assert result.writes_attempted == 1
    assert result.operations[0].status == "failed"
    assert result.failure is not None
    assert result.failure.code == "apply.write_rejected"


def test_put_server_error_indeterminate() -> None:
    plan = _create_plan()
    with (
        start_contract_server(list_mode="empty", put_mode="server_error") as server,
        make_loopback_client(server.base_url) as client,
    ):
        result = execute_governance_plan(plan, client, mode=ExecutionMode.APPLY)
    assert result.status == "indeterminate"
    assert result.writes_unknown == 1
    assert result.operations[0].status == "unknown"
    assert result.failure is not None
    assert result.failure.code == "apply.write_outcome_unknown"


def test_put_bad_json_still_applied() -> None:
    plan = _create_plan()
    with (
        start_contract_server(list_mode="empty", put_mode="ok_bad_json") as server,
        make_loopback_client(server.base_url) as client,
    ):
        result = execute_governance_plan(plan, client, mode=ExecutionMode.APPLY)
    assert result.status == "applied"
    assert result.writes_performed == 1


class _CountingCredential(FakeTokenCredential):
    def __init__(self, token: str, *, fail_after: int) -> None:
        super().__init__(token)
        self._fail_after = fail_after
        self._calls = 0

    def get_token(self, *scopes: str, **kwargs: object):
        self._calls += 1
        if self._calls > self._fail_after:
            raise RuntimeError("SECRET_SENTINEL_token_boom")
        return super().get_token(*scopes, **kwargs)


def test_auth_failure_first_mutation_write_failed() -> None:
    plan = _create_plan()
    # GETs for empty list = 1 token; first PUT needs another → fail after 1 GET.
    token = AUTH_SENTINEL.removeprefix("Bearer ").strip()
    provider = PurviewAuthorizationProvider(_CountingCredential(token, fail_after=1))  # type: ignore[arg-type]
    with start_contract_server(list_mode="empty", put_mode="created") as server:
        with make_loopback_client(server.base_url, auth_provider=provider) as client:
            result = execute_governance_plan(plan, client, mode=ExecutionMode.APPLY)
        assert result.status == "write-failed"
        assert result.failure is not None
        assert result.failure.code == "apply.write_auth_failed"
        assert result.writes_performed == 0
        assert result.writes_attempted == 1
        assert not any(r.method == "PUT" for r in server.state.recordings)
        assert "SECRET_SENTINEL_token_boom" not in result.to_canonical_json()


def test_auth_failure_after_successful_prefix() -> None:
    from purview_governance.config import validate_config_text

    yaml_text = """
apiVersion: purview-governance-config/v1
target:
  endpoint: https://account.purview.azure.com
authentication:
  strategy: defaultAzureCredential
resources:
  - type: dataSource
    name: alpha-source
    kind: AzureStorage
    properties:
      endpoint: https://alpha.blob.core.windows.net/
      collection:
        referenceName: root
  - type: dataSource
    name: beta-source
    kind: AzureStorage
    properties:
      endpoint: https://beta.blob.core.windows.net/
      collection:
        referenceName: root
  - type: dataSource
    name: gamma-source
    kind: AzureStorage
    properties:
      endpoint: https://gamma.blob.core.windows.net/
      collection:
        referenceName: root
"""
    plan = build_governance_plan(
        validate_config_text(yaml_text, format_hint="yaml"), empty_remote()
    )
    token = AUTH_SENTINEL.removeprefix("Bearer ").strip()
    # call1=list GET, call2=PUT alpha, call3=auth for beta fails
    provider = PurviewAuthorizationProvider(_CountingCredential(token, fail_after=2))  # type: ignore[arg-type]
    with start_contract_server(list_mode="empty", put_mode="created") as server:
        with make_loopback_client(server.base_url, auth_provider=provider) as client:
            result = execute_governance_plan(plan, client, mode=ExecutionMode.APPLY)
        assert result.status == "write-failed"
        assert result.failure is not None
        assert result.failure.code == "apply.write_auth_failed"
        assert result.writes_performed == 1
        assert result.writes_attempted == 2
        assert [op.status for op in result.operations] == ["succeeded", "failed", "not-run"]
        puts = [r for r in server.state.recordings if r.method == "PUT"]
        assert len(puts) == 1
        assert puts[0].path == "/scan/datasources/alpha-source"
        blob = result.to_canonical_json()
        assert "SECRET_SENTINEL_token_boom" not in blob


def test_target_endpoint_property_on_public_client() -> None:
    provider = PurviewAuthorizationProvider(FakeTokenCredential("t"))  # type: ignore[arg-type]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"value": []})

    with PurviewScanningClient(
        "https://account.purview.azure.com",
        provider,
        transport=httpx.MockTransport(handler),
    ) as client:
        assert client.target_endpoint == "https://account.purview.azure.com"
