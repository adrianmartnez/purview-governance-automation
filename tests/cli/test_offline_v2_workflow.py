"""Offline CLI reviewer workflow for config/plan/apply v2 (loopback DI)."""

from __future__ import annotations

import contextlib
import json
from io import StringIO
from pathlib import Path

from purview_governance.apply import RESULT_API_VERSION_V2, load_execution_result_file
from purview_governance.cli import EXIT_SUCCESS, _CliDependencies, _run
from purview_governance.config.models import CONFIG_API_VERSION_V2
from purview_governance.plan import PLAN_API_VERSION_V2, load_plan_file
from purview_governance.remote_state import REMOTE_STATE_API_VERSION_V2
from tests.contract.client_helpers import make_loopback_client
from tests.contract.server import start_contract_server

_REPO_ROOT = Path(__file__).resolve().parents[2]
_EXAMPLE_V2 = _REPO_ROOT / "examples" / "fictional-governance-config-v2.yaml"

_EXPECTED_PUT_PATHS = [
    "/scan/datasources/ds-a",
    "/scan/datasources/ds-b",
    "/scan/classificationrules/custom-rule",
    "/scan/scanrulesets/custom-srs",
    "/scan/datasources/ds-a/scans/DailyScan",
    "/scan/datasources/ds-b/scans/DailyScan",
]


def test_offline_v2_workflow(tmp_path: Path) -> None:
    assert _EXAMPLE_V2.is_file(), f"missing public example: {_EXAMPLE_V2}"
    config_path = _EXAMPLE_V2
    remote_path = tmp_path / "remote.json"
    plan_path = tmp_path / "plan.json"
    dry_result_path = tmp_path / "dry-result.json"
    result_path = tmp_path / "result.json"
    replan_path = tmp_path / "replan.json"
    noop_result_path = tmp_path / "noop-result.json"

    with start_contract_server(list_mode="empty", put_mode="created") as server:

        def factory(endpoint: str):
            assert endpoint.startswith("https://")
            return make_loopback_client(server.base_url, logical_target_endpoint=endpoint)

        deps = _CliDependencies(scanning_client_factory=factory)

        # A — config validate
        validate_buf = StringIO()
        with contextlib.redirect_stdout(validate_buf):
            assert (
                _run(["config", "validate", str(config_path), "--json"], deps=deps) == EXIT_SUCCESS
            )
        validate_doc = json.loads(validate_buf.getvalue())
        assert validate_doc["status"] == "valid"
        assert validate_doc["apiVersion"] == CONFIG_API_VERSION_V2

        # B — independent remote-state capture (audit snapshot; not plan input)
        assert (
            _run(
                [
                    "remote-state",
                    "capture",
                    str(config_path),
                    "--output",
                    str(remote_path),
                ],
                deps=deps,
            )
            == EXIT_SUCCESS
        )
        remote_doc = json.loads(remote_path.read_text(encoding="utf-8"))
        assert remote_doc["apiVersion"] == REMOTE_STATE_API_VERSION_V2
        assert remote_doc["dataSources"] == []
        assert remote_doc["classificationRules"] == []
        assert remote_doc["scanRuleSets"] == []
        assert remote_doc["scans"] == []

        # C — plan create (fresh capture + desired-vs-remote comparison + plan)
        assert (
            _run(
                ["plan", "create", str(config_path), "--output", str(plan_path)],
                deps=deps,
            )
            == EXIT_SUCCESS
        )
        plan = load_plan_file(plan_path)
        assert plan.api_version == PLAN_API_VERSION_V2
        assert len(plan.operations) == 6
        assert all(op.action == "create" for op in plan.operations)
        assert plan.summary.create == 6
        assert plan.summary.replace == 0

        # D — plan inspect
        assert _run(["plan", "inspect", str(plan_path)], deps=deps) == EXIT_SUCCESS

        # E — dry-run apply (fresh staleness capture; zero PUT)
        assert (
            _run(
                [
                    "apply",
                    str(plan_path),
                    "--result",
                    str(dry_result_path),
                ],
                deps=deps,
            )
            == EXIT_SUCCESS
        )
        dry = load_execution_result_file(dry_result_path)
        assert dry.api_version == RESULT_API_VERSION_V2
        assert dry.status == "dry-run-ready"
        assert dry.writes_attempted == 0
        assert not any(r.method == "PUT" for r in server.state.recordings)

        # F — explicit controlled apply
        assert (
            _run(
                [
                    "apply",
                    str(plan_path),
                    "--apply",
                    "--result",
                    str(result_path),
                ],
                deps=deps,
            )
            == EXIT_SUCCESS
        )
        applied = load_execution_result_file(result_path)
        assert applied.api_version == RESULT_API_VERSION_V2
        assert applied.status == "applied"
        assert applied.writes_performed == 6
        puts = [r for r in server.state.recordings if r.method == "PUT"]
        assert len(puts) == 6
        assert [r.path for r in puts] == _EXPECTED_PUT_PATHS

        # G — result inspect
        assert _run(["result", "inspect", str(result_path)], deps=deps) == EXIT_SUCCESS

        # H — re-plan after apply (fresh capture → converged empty operations)
        assert (
            _run(
                ["plan", "create", str(config_path), "--output", str(replan_path)],
                deps=deps,
            )
            == EXIT_SUCCESS
        )
        replan = load_plan_file(replan_path)
        assert replan.api_version == PLAN_API_VERSION_V2
        assert replan.operations == ()
        assert replan.summary.create == 0
        assert replan.summary.replace == 0

        # I — no-op apply on empty replan (PUT count must remain 6)
        assert (
            _run(
                [
                    "apply",
                    str(replan_path),
                    "--apply",
                    "--result",
                    str(noop_result_path),
                ],
                deps=deps,
            )
            == EXIT_SUCCESS
        )
        noop = load_execution_result_file(noop_result_path)
        assert noop.api_version == RESULT_API_VERSION_V2
        assert noop.status == "applied"
        assert noop.writes_attempted == 0
        puts_after = [r for r in server.state.recordings if r.method == "PUT"]
        assert len(puts_after) == 6
