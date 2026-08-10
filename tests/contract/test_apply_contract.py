"""Offline API contract tests for safe apply workflow."""

from __future__ import annotations

import pytest

from purview_governance.apply import ExecutionMode, execute_governance_plan
from purview_governance.plan import build_governance_plan
from tests.contract.client_helpers import make_loopback_client
from tests.contract.server import start_contract_server
from tests.plan.helpers import create_config, empty_remote


def _three_create_plan():
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
    return build_governance_plan(
        validate_config_text(yaml_text, format_hint="yaml"), empty_remote()
    )


@pytest.mark.api_contract
def test_contract_dry_run_zero_put() -> None:
    plan = build_governance_plan(create_config(), empty_remote())
    with (
        start_contract_server(list_mode="empty") as server,
        make_loopback_client(server.base_url) as client,
    ):
        result = execute_governance_plan(plan, client)
    assert result.status == "dry-run-ready"
    assert not any(r.method == "PUT" for r in server.state.recordings)


@pytest.mark.api_contract
def test_contract_apply_exact_put() -> None:
    plan = build_governance_plan(create_config(), empty_remote())
    expected = {
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
            put_expected_body=expected,
        ) as server,
        make_loopback_client(server.base_url) as client,
    ):
        result = execute_governance_plan(plan, client, mode=ExecutionMode.APPLY)
    assert result.status == "applied"
    puts = [r for r in server.state.recordings if r.method == "PUT"]
    assert len(puts) == 1
    assert puts[0].json_body == expected
    assert puts[0].authorization_valid is True
    assert "Authorization" not in repr(puts[0])


@pytest.mark.api_contract
def test_contract_stale_zero_put() -> None:
    plan = build_governance_plan(create_config(), empty_remote())
    with (
        start_contract_server(list_mode="one_page") as server,
        make_loopback_client(server.base_url) as client,
    ):
        result = execute_governance_plan(plan, client, mode=ExecutionMode.APPLY)
    assert result.status == "stale"
    assert not any(r.method == "PUT" for r in server.state.recordings)


@pytest.mark.api_contract
def test_contract_wrong_target_zero_put() -> None:
    plan = build_governance_plan(create_config(), empty_remote())
    with (
        start_contract_server(list_mode="empty") as server,
        make_loopback_client(
            server.base_url,
            logical_target_endpoint="https://other.purview.azure.com",
        ) as client,
    ):
        result = execute_governance_plan(plan, client, mode=ExecutionMode.APPLY)
    assert result.status == "wrong-target"
    assert server.state.recordings == []


@pytest.mark.api_contract
def test_contract_client_error_no_retry() -> None:
    plan = build_governance_plan(create_config(), empty_remote())
    with (
        start_contract_server(list_mode="empty", put_mode="client_error") as server,
        make_loopback_client(server.base_url) as client,
    ):
        result = execute_governance_plan(plan, client, mode=ExecutionMode.APPLY)
    assert result.status == "write-failed"
    assert len([r for r in server.state.recordings if r.method == "PUT"]) == 1


@pytest.mark.api_contract
def test_contract_disconnect_indeterminate() -> None:
    plan = build_governance_plan(create_config(), empty_remote())
    with (
        start_contract_server(list_mode="empty", put_mode="disconnect_after_record") as server,
        make_loopback_client(server.base_url) as client,
    ):
        result = execute_governance_plan(plan, client, mode=ExecutionMode.APPLY)
    assert result.status == "indeterminate"
    assert result.writes_unknown == 1
    assert len([r for r in server.state.recordings if r.method == "PUT"]) == 1


@pytest.mark.api_contract
def test_contract_multi_op_second_client_error_stops() -> None:
    plan = _three_create_plan()
    assert [op.name for op in plan.operations] == [
        "alpha-source",
        "beta-source",
        "gamma-source",
    ]
    with (
        start_contract_server(
            list_mode="empty",
            put_mode="script",
            put_script=["created", "client_error", "created"],
        ) as server,
        make_loopback_client(server.base_url) as client,
    ):
        result = execute_governance_plan(plan, client, mode=ExecutionMode.APPLY)
    assert result.status == "write-failed"
    assert result.writes_performed == 1
    assert result.writes_attempted == 2
    assert [op.status for op in result.operations] == ["succeeded", "failed", "not-run"]
    puts = [r for r in server.state.recordings if r.method == "PUT"]
    assert len(puts) == 2
    assert puts[0].path == "/scan/datasources/alpha-source"
    assert puts[1].path == "/scan/datasources/beta-source"


@pytest.mark.api_contract
def test_contract_multi_op_second_server_error_indeterminate() -> None:
    plan = _three_create_plan()
    with (
        start_contract_server(
            list_mode="empty",
            put_mode="script",
            put_script=["created", "server_error", "created"],
        ) as server,
        make_loopback_client(server.base_url) as client,
    ):
        result = execute_governance_plan(plan, client, mode=ExecutionMode.APPLY)
    assert result.status == "indeterminate"
    assert result.writes_performed == 1
    assert result.writes_attempted == 2
    assert result.writes_unknown == 1
    assert [op.status for op in result.operations] == ["succeeded", "unknown", "not-run"]
    puts = [r for r in server.state.recordings if r.method == "PUT"]
    assert len(puts) == 2
    assert puts[0].path == "/scan/datasources/alpha-source"
    assert puts[1].path == "/scan/datasources/beta-source"
