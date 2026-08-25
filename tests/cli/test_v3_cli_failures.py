"""Negative CLI matrix for Unified Catalog (v3) flags and fail-closed paths."""

from __future__ import annotations

from pathlib import Path

import pytest

from purview_governance.cli import (
    EXIT_SAFETY,
    EXIT_VALIDATION,
    _CliDependencies,
    _run,
)
from purview_governance.config.models_v3 import CONFIG_API_VERSION_V3
from purview_governance.plan import build_governance_plan
from purview_governance.unified_catalog.client import PurviewUnifiedCatalogClient
from tests.apply.helpers_v3 import (
    DOMAIN_A,
    OWNER_ID,
    TENANT_ID,
    TERM_PARENT,
    apply_server,
    base_config_header,
    build_plan_from_yaml,
    capture_remote_for_apply,
    make_tenant_bound_client,
)
from tests.apply.test_blocked_short_circuit_v3 import _blocked_plan_and_remote
from tests.auth.tenant_bound_fakes import OfflineClientSecretCredential
from tests.contract.auth import AUTH_SENTINEL
from tests.plan.helpers import create_config, empty_remote

_SECRET = "sentinel-secret-value"
_TOKEN = "must-not-leak-raw-token"


def test_v1_plan_create_rejects_credential_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("AZURE_CLIENT_SECRET", _SECRET)
    config_path = tmp_path / "cfg-v1.yaml"
    config_path.write_text(
        """
apiVersion: purview-governance-config/v1
target:
  endpoint: https://contoso-fictional.purview.azure.com
authentication:
  strategy: defaultAzureCredential
resources: []
""",
        encoding="utf-8",
    )
    code = _run(
        [
            "plan",
            "create",
            str(config_path),
            "--output",
            str(tmp_path / "plan.json"),
            "--credential",
            "client-secret",
        ]
    )
    assert code == EXIT_VALIDATION
    assert "cli.credential_flag_unsupported" in capsys.readouterr().err


def test_v2_remote_capture_rejects_credential_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("AZURE_CLIENT_SECRET", _SECRET)
    config_path = tmp_path / "cfg-v2.yaml"
    config_path.write_text(
        """
apiVersion: purview-governance-config/v2
target:
  endpoint: https://contoso-fictional.purview.azure.com
authentication:
  strategy: defaultAzureCredential
resources: []
""",
        encoding="utf-8",
    )
    code = _run(
        [
            "remote-state",
            "capture",
            str(config_path),
            "--output",
            str(tmp_path / "remote.json"),
            "--credential",
            "azure-cli",
        ]
    )
    assert code == EXIT_VALIDATION
    assert "cli.credential_flag_unsupported" in capsys.readouterr().err


def test_v1_apply_rejects_credential_no_http(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("AZURE_CLIENT_SECRET", _SECRET)
    plan = build_governance_plan(create_config(), empty_remote())
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(plan.to_canonical_json(), encoding="utf-8")

    http_calls = {"count": 0}

    def exploding_factory(endpoint: str):
        http_calls["count"] += 1
        raise AssertionError(f"must not build scanning client for {endpoint}")

    code = _run(
        ["apply", str(plan_path), "--credential", "client-secret"],
        deps=_CliDependencies(scanning_client_factory=exploding_factory),
    )
    assert code == EXIT_VALIDATION
    assert http_calls["count"] == 0
    err = capsys.readouterr().err
    assert "cli.credential_flag_unsupported" in err
    assert _SECRET not in err


def test_v3_plan_create_requires_remote_state_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = tmp_path / "cfg-v3.yaml"
    config_path.write_text(
        f"""
apiVersion: {CONFIG_API_VERSION_V3}
target:
  surface: unifiedCatalog
  tenantId: {TENANT_ID}
authentication:
  strategy: defaultAzureCredential
resources: []
""",
        encoding="utf-8",
    )
    code = _run(["plan", "create", str(config_path), "--output", str(tmp_path / "plan.json")])
    assert code == EXIT_VALIDATION
    assert "cli.remote_state_output_required" in capsys.readouterr().err


def test_v3_apply_requires_remote_state(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    plan, remote = _blocked_plan_and_remote()
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(plan.to_canonical_json(), encoding="utf-8")
    del remote
    code = _run(["apply", str(plan_path)])
    assert code == EXIT_VALIDATION
    assert "cli.remote_state_required" in capsys.readouterr().err


def test_ready_apply_requires_credential(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    yaml_text = (
        base_config_header()
        + f"""
  - type: glossaryTerm
    id: {TERM_PARENT}
    properties:
      name: parent-term
      domain: {DOMAIN_A}
      description: Parent term
      owners:
        - id: {OWNER_ID}
"""
    )
    with apply_server() as server:
        client = make_tenant_bound_client(server.base_url)
        try:
            remote = capture_remote_for_apply(client, include_glossary_terms=True)
            plan = build_plan_from_yaml(yaml_text, remote)
        finally:
            client.close()

    assert plan.execution_eligibility == "ready"
    plan_path = tmp_path / "plan.json"
    remote_path = tmp_path / "remote.json"
    plan_path.write_text(plan.to_canonical_json(), encoding="utf-8")
    remote_path.write_text(remote.to_canonical_json(), encoding="utf-8")

    code = _run(
        ["apply", str(plan_path), "--remote-state", str(remote_path)],
    )
    assert code == EXIT_VALIDATION
    assert "cli.credential_required" in capsys.readouterr().err


def test_invalid_local_remote_exits_before_auth(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("AZURE_CLIENT_SECRET", _SECRET)
    yaml_text = (
        base_config_header()
        + f"""
  - type: glossaryTerm
    id: {TERM_PARENT}
    properties:
      name: parent-term
      domain: {DOMAIN_A}
      description: Parent term
      owners:
        - id: {OWNER_ID}
"""
    )
    with apply_server() as server:
        client = make_tenant_bound_client(server.base_url)
        try:
            remote = capture_remote_for_apply(client, include_glossary_terms=True)
            plan = build_plan_from_yaml(yaml_text, remote)
        finally:
            client.close()

    plan_path = tmp_path / "plan.json"
    remote_path = tmp_path / "remote.json"
    plan_path.write_text(plan.to_canonical_json(), encoding="utf-8")
    remote_path.write_text("{not-valid-json", encoding="utf-8")

    token_calls = {"count": 0}
    http_calls = {"count": 0}

    def credential_provider_factory(
        selector: str | None,
        *,
        tenant_id: str,
        endpoint: str | None = None,
        tenant_bound: bool = False,
    ):
        del selector, tenant_id, endpoint, tenant_bound
        token_calls["count"] += 1
        raise AssertionError("credential factory must not run for invalid remote")

    def uc_factory(endpoint: str, provider):
        http_calls["count"] += 1
        raise AssertionError(f"UC client must not be built for {endpoint}")

    code = _run(
        [
            "apply",
            str(plan_path),
            "--remote-state",
            str(remote_path),
            "--credential",
            "client-secret",
        ],
        deps=_CliDependencies(
            unified_catalog_client_factory=uc_factory,
            credential_provider_factory=credential_provider_factory,
        ),
    )
    assert code == EXIT_VALIDATION
    assert token_calls["count"] == 0
    assert http_calls["count"] == 0
    err = capsys.readouterr().err
    assert "remote_state.invalid_syntax" in err
    assert _SECRET not in err


def test_blocked_apply_without_credential_zero_token_http(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("AZURE_CLIENT_SECRET", _SECRET)
    plan, remote = _blocked_plan_and_remote()
    plan_path = tmp_path / "plan.json"
    remote_path = tmp_path / "remote.json"
    plan_path.write_text(plan.to_canonical_json(), encoding="utf-8")
    remote_path.write_text(remote.to_canonical_json(), encoding="utf-8")

    token_calls = {"count": 0}

    with apply_server() as server:

        def uc_factory(endpoint: str, provider):
            original_acquire = provider.acquire_authorization_header

            def tracking_acquire() -> str:
                token_calls["count"] += 1
                return original_acquire()

            provider.acquire_authorization_header = tracking_acquire  # type: ignore[method-assign]
            return PurviewUnifiedCatalogClient._from_loopback_base_url(
                server.base_url,
                provider,
                logical_target_endpoint=endpoint,
            )

        code = _run(
            ["apply", str(plan_path), "--remote-state", str(remote_path), "--json"],
            deps=_CliDependencies(unified_catalog_client_factory=uc_factory),
        )

    assert code == EXIT_SAFETY
    assert token_calls["count"] == 0
    assert server.state.recordings == []
    out = capsys.readouterr().out
    assert '"status":"blocked"' in out.replace(" ", "")
    assert _SECRET not in out


def test_ready_apply_stdout_stderr_do_not_leak_secrets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from purview_governance.auth.provider import PurviewAuthorizationProvider
    from purview_governance.auth.tenant_bound import TenantBoundAuthorizationProvider
    from purview_governance.cli import EXIT_SUCCESS

    monkeypatch.setenv("AZURE_CLIENT_SECRET", _SECRET)
    monkeypatch.setenv("AZURE_CLIENT_ID", "00000000-0000-4000-8000-000000000099")

    yaml_text = (
        base_config_header()
        + f"""
  - type: glossaryTerm
    id: {TERM_PARENT}
    properties:
      name: parent-term
      domain: {DOMAIN_A}
      description: Parent term
      owners:
        - id: {OWNER_ID}
"""
    )
    with apply_server() as server:
        client = make_tenant_bound_client(server.base_url)
        try:
            remote = capture_remote_for_apply(client, include_glossary_terms=True)
            plan = build_plan_from_yaml(yaml_text, remote)
        finally:
            client.close()

        plan_path = tmp_path / "plan.json"
        remote_path = tmp_path / "remote.json"
        result_path = tmp_path / "result.json"
        plan_path.write_text(plan.to_canonical_json(), encoding="utf-8")
        remote_path.write_text(remote.to_canonical_json(), encoding="utf-8")

        offline_token = AUTH_SENTINEL.removeprefix("Bearer ").strip()

        def credential_provider_factory(
            selector: str | None,
            *,
            tenant_id: str,
            endpoint: str | None = None,
            tenant_bound: bool = False,
        ):
            del selector
            credential = OfflineClientSecretCredential(token=offline_token)
            if tenant_bound:
                assert endpoint is not None
                return TenantBoundAuthorizationProvider(
                    credential,
                    tenant_id=tenant_id,
                    endpoint=endpoint,
                )
            return PurviewAuthorizationProvider(credential)

        def uc_factory(endpoint: str, provider):
            return PurviewUnifiedCatalogClient._from_loopback_base_url(
                server.base_url,
                provider,
                logical_target_endpoint=endpoint,
            )

        code = _run(
            [
                "apply",
                str(plan_path),
                "--remote-state",
                str(remote_path),
                "--credential",
                "client-secret",
                "--result",
                str(result_path),
                "--json",
            ],
            deps=_CliDependencies(
                unified_catalog_client_factory=uc_factory,
                credential_provider_factory=credential_provider_factory,
            ),
        )

    assert code == EXIT_SUCCESS
    captured = capsys.readouterr()
    blob = captured.out + captured.err
    assert _SECRET not in blob
    assert _TOKEN not in blob
    assert "Bearer " not in blob


def test_apply_result_cannot_alias_remote_state_even_with_force(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    plan, remote = _blocked_plan_and_remote()
    plan_path = tmp_path / "plan.json"
    remote_path = tmp_path / "remote.json"
    plan_path.write_text(plan.to_canonical_json(), encoding="utf-8")
    remote_path.write_text(remote.to_canonical_json(), encoding="utf-8")

    code = _run(
        [
            "apply",
            str(plan_path),
            "--remote-state",
            str(remote_path),
            "--result",
            str(remote_path),
            "--force",
        ]
    )
    assert code == EXIT_VALIDATION
    assert "cli.output_aliases_input" in capsys.readouterr().err
