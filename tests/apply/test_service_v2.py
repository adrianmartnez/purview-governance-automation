"""Controlled multi-resource apply (plan/v2 → execution-result/v2)."""

from __future__ import annotations

from purview_governance.apply import ExecutionMode, execute_governance_plan
from purview_governance.apply.identity import RESULT_API_VERSION_V2
from purview_governance.auth import PurviewAuthorizationProvider
from purview_governance.config import validate_config_text
from purview_governance.plan import build_governance_plan_v2
from purview_governance.remote_state import capture_remote_state_v2
from tests.apply.test_service import _CountingCredential
from tests.contract.client_helpers import make_loopback_client
from tests.contract.server import AUTH_SENTINEL, start_contract_server

_MIXED = """
apiVersion: purview-governance-config/v2
target:
  endpoint: https://account.purview.azure.com
authentication:
  strategy: defaultAzureCredential
resources:
  - type: dataSource
    name: ds-a
    kind: AzureStorage
    properties:
      endpoint: https://a.blob.core.windows.net/
      collection:
        referenceName: root
  - type: dataSource
    name: ds-b
    kind: AzureStorage
    properties:
      endpoint: https://b.blob.core.windows.net/
      collection:
        referenceName: root
  - type: classificationRule
    name: custom-rule
    kind: Custom
    properties:
      classificationName: Contoso.Secret
      minimumPercentageMatch: 80.0
      ruleStatus: Enabled
      dataPatterns:
        - kind: Regex
          pattern: "^[0-9]+$"
      columnPatterns:
        - kind: Regex
          pattern: "^col$"
  - type: scanRuleSet
    name: custom-srs
    kind: AzureStorage
    scanRulesetType: Custom
    properties:
      scanningRule:
        fileExtensions: [CSV, JSON]
      excludedSystemClassifications: []
      includedCustomClassificationRuleNames: [custom-rule]
  - type: scan
    name: DailyScan
    kind: AzureStorageMsi
    properties:
      dataSourceName: ds-a
      scanRulesetName: custom-srs
      scanRulesetType: Custom
      collection:
        referenceName: root
  - type: scan
    name: DailyScan
    kind: AzureStorageMsi
    properties:
      dataSourceName: ds-b
      scanRulesetName: AzureStorage
      scanRulesetType: System
      collection:
        referenceName: root
"""


def _plan_against_empty_server(server, client):
    config = validate_config_text(_MIXED, format_hint="yaml")
    remote = capture_remote_state_v2(client)
    return build_governance_plan_v2(config, remote)


def test_mixed_apply_order_and_scan_bodies() -> None:
    with (
        start_contract_server(list_mode="empty", put_mode="created") as server,
        make_loopback_client(server.base_url) as client,
    ):
        plan = _plan_against_empty_server(server, client)
        result = execute_governance_plan(plan, client, mode=ExecutionMode.APPLY)
    assert result.status == "applied"
    assert result.api_version == RESULT_API_VERSION_V2
    assert result.writes_performed == 6
    puts = [r for r in server.state.recordings if r.method == "PUT"]
    assert [r.path for r in puts] == [
        "/scan/datasources/ds-a",
        "/scan/datasources/ds-b",
        "/scan/classificationrules/custom-rule",
        "/scan/scanrulesets/custom-srs",
        "/scan/datasources/ds-a/scans/DailyScan",
        "/scan/datasources/ds-b/scans/DailyScan",
    ]
    scan_puts = puts[-2:]
    assert scan_puts[0].json_body["dataSourceName"] == "ds-a"
    assert scan_puts[1].json_body["dataSourceName"] == "ds-b"
    scan_ops = [op for op in result.operations if op.resource_type == "scan"]
    assert {(op.data_source_name, op.name) for op in scan_ops} == {
        ("ds-a", "DailyScan"),
        ("ds-b", "DailyScan"),
    }


def test_dry_run_reaches_staleness_gate_zero_puts() -> None:
    with (
        start_contract_server(list_mode="empty") as server,
        make_loopback_client(server.base_url) as client,
    ):
        plan = _plan_against_empty_server(server, client)
        before = len(server.state.recordings)
        result = execute_governance_plan(plan, client, mode=ExecutionMode.DRY_RUN)
        assert result.status == "dry-run-ready"
        assert result.writes_attempted == 0
        assert not any(r.method == "PUT" for r in server.state.recordings)
        assert len(server.state.recordings) > before  # fresh capture GETs


def test_stale_zero_puts() -> None:
    with (
        start_contract_server(list_mode="empty", put_mode="created") as server,
        make_loopback_client(server.base_url) as client,
    ):
        plan = _plan_against_empty_server(server, client)
        # Mutate remote inventory after planning.
        server.state.list_mode = "one_page"
        result = execute_governance_plan(plan, client, mode=ExecutionMode.APPLY)
    assert result.status == "stale"
    assert result.writes_attempted == 0
    assert not any(r.method == "PUT" for r in server.state.recordings)


def test_http_4xx_matrix() -> None:
    for mode, code in (
        ("bad_request", "apply.write_rejected"),
        ("unauthorized", "apply.write_rejected"),
        ("forbidden", "apply.write_rejected"),
        ("client_error", "apply.write_rejected"),
        ("server_error", "apply.write_outcome_unknown"),
    ):
        with (
            start_contract_server(list_mode="empty", put_mode=mode) as server,
            make_loopback_client(server.base_url) as client,
        ):
            plan = _plan_against_empty_server(server, client)
            result = execute_governance_plan(plan, client, mode=ExecutionMode.APPLY)
        if mode == "server_error":
            assert result.status == "indeterminate"
        else:
            assert result.status == "write-failed"
        assert result.failure is not None
        assert result.failure.code == code
        assert result.writes_attempted == 1
        assert result.operations[0].status in {"failed", "unknown"}
        assert all(op.status == "not-run" for op in result.operations[1:])


def test_auth_error_write_auth_failed() -> None:
    token = AUTH_SENTINEL.removeprefix("Bearer ").strip()
    config = validate_config_text(_MIXED, format_hint="yaml")
    # Empty remote-state/v2 capture issues three LIST GETs (DS/CR/SRS); fourth
    # token acquisition is the first PUT → AuthenticationError.
    provider = PurviewAuthorizationProvider(_CountingCredential(token, fail_after=3))  # type: ignore[arg-type]
    with start_contract_server(list_mode="empty", put_mode="created") as server:
        with make_loopback_client(server.base_url) as planner:
            remote = capture_remote_state_v2(planner)
            plan = build_governance_plan_v2(config, remote)
        with make_loopback_client(server.base_url, auth_provider=provider) as client:
            result = execute_governance_plan(plan, client, mode=ExecutionMode.APPLY)
        assert result.status == "write-failed"
        assert result.failure is not None
        assert result.failure.code == "apply.write_auth_failed"
        assert result.writes_performed == 0
        assert result.writes_attempted == 1
        assert not any(r.method == "PUT" for r in server.state.recordings)


def test_partial_success_stops_later_writes() -> None:
    with (
        start_contract_server(
            list_mode="empty",
            put_mode="script",
            put_script=["created", "client_error"],
        ) as server,
        make_loopback_client(server.base_url) as client,
    ):
        plan = _plan_against_empty_server(server, client)
        result = execute_governance_plan(plan, client, mode=ExecutionMode.APPLY)
    assert result.status == "write-failed"
    assert result.writes_performed == 1
    assert result.writes_attempted == 2
    assert [op.status for op in result.operations[:3]] == ["succeeded", "failed", "not-run"]
    puts = [r for r in server.state.recordings if r.method == "PUT"]
    assert len(puts) == 2


def test_idempotent_replan_dual_daily_scan() -> None:
    with (
        start_contract_server(list_mode="empty", put_mode="created") as server,
        make_loopback_client(server.base_url) as client,
    ):
        config = validate_config_text(_MIXED, format_hint="yaml")
        remote = capture_remote_state_v2(client)
        plan = build_governance_plan_v2(config, remote)
        first = execute_governance_plan(plan, client, mode=ExecutionMode.APPLY)
        assert first.status == "applied"
        remote_after = capture_remote_state_v2(client)
        replan = build_governance_plan_v2(config, remote_after)
        assert replan.operations == ()
        assert replan.summary.create == 0
        assert replan.summary.replace == 0
        second = execute_governance_plan(replan, client, mode=ExecutionMode.APPLY)
        assert second.status == "applied"
        assert second.writes_attempted == 0
        assert ("ds-a", "DailyScan") in server.state.scan_bodies
        assert ("ds-b", "DailyScan") in server.state.scan_bodies
