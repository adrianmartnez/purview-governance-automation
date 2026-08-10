"""CLI path protection, apply dry-run/apply, and offline workflow tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from purview_governance.cli import (
    EXIT_PERSIST,
    EXIT_PREWRITE,
    EXIT_SAFETY,
    EXIT_SUCCESS,
    EXIT_VALIDATION,
    EXIT_WRITE,
    _CliDependencies,
    _run,
)
from purview_governance.plan import build_governance_plan
from tests.contract.client_helpers import make_loopback_client
from tests.contract.server import start_contract_server
from tests.plan.helpers import CREATE_CONFIG_YAML, EMPTY_CONFIG_YAML, create_config, empty_remote


def test_config_validate_offline(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = tmp_path / "cfg.yaml"
    config.write_text(EMPTY_CONFIG_YAML, encoding="utf-8")
    assert _run(["config", "validate", str(config)]) == EXIT_SUCCESS
    assert "config valid" in capsys.readouterr().out


def test_plan_inspect_offline(tmp_path: Path) -> None:
    plan = build_governance_plan(create_config(), empty_remote())
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(plan.to_canonical_json(), encoding="utf-8")
    assert _run(["plan", "inspect", str(plan_path)]) == EXIT_SUCCESS


def test_apply_result_cannot_alias_plan_even_with_force(tmp_path: Path) -> None:
    plan = build_governance_plan(create_config(), empty_remote())
    plan_path = tmp_path / "plan.json"
    original = plan.to_canonical_json()
    plan_path.write_text(original, encoding="utf-8")
    code = _run(
        ["apply", str(plan_path), "--apply", "--result", str(plan_path), "--force"],
    )
    assert code == EXIT_VALIDATION
    assert plan_path.read_text(encoding="utf-8") == original


def test_apply_dry_run_and_apply_with_di(tmp_path: Path) -> None:
    plan = build_governance_plan(create_config(), empty_remote())
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(plan.to_canonical_json(), encoding="utf-8")
    result_path = tmp_path / "result.json"

    with start_contract_server(list_mode="empty", put_mode="created") as server:

        def factory(endpoint: str):
            assert endpoint.startswith("https://")
            return make_loopback_client(server.base_url, logical_target_endpoint=endpoint)

        deps = _CliDependencies(scanning_client_factory=factory)
        dry = _run(["apply", str(plan_path), "--json"], deps=deps)
        assert dry == EXIT_SUCCESS
        assert not any(r.method == "PUT" for r in server.state.recordings)

        applied = _run(
            ["apply", str(plan_path), "--apply", "--result", str(result_path), "--json"],
            deps=deps,
        )
        assert applied == EXIT_SUCCESS
        assert result_path.is_file()
        assert len([r for r in server.state.recordings if r.method == "PUT"]) == 1


def test_offline_v1_workflow(tmp_path: Path) -> None:
    config_path = tmp_path / "cfg.yaml"
    config_path.write_text(CREATE_CONFIG_YAML, encoding="utf-8")
    remote_path = tmp_path / "remote.json"
    plan_path = tmp_path / "plan.json"
    result_path = tmp_path / "result.json"

    with start_contract_server(list_mode="empty", put_mode="created") as server:

        def factory(endpoint: str):
            return make_loopback_client(server.base_url, logical_target_endpoint=endpoint)

        deps = _CliDependencies(scanning_client_factory=factory)
        assert _run(["config", "validate", str(config_path)], deps=deps) == EXIT_SUCCESS
        assert (
            _run(
                ["remote-state", "capture", str(config_path), "--output", str(remote_path)],
                deps=deps,
            )
            == EXIT_SUCCESS
        )
        assert (
            _run(
                ["plan", "create", str(config_path), "--output", str(plan_path)],
                deps=deps,
            )
            == EXIT_SUCCESS
        )
        assert _run(["plan", "inspect", str(plan_path)], deps=deps) == EXIT_SUCCESS
        assert _run(["apply", str(plan_path)], deps=deps) == EXIT_SUCCESS
        assert (
            _run(
                ["apply", str(plan_path), "--apply", "--result", str(result_path)],
                deps=deps,
            )
            == EXIT_SUCCESS
        )
        assert _run(["result", "inspect", str(result_path)], deps=deps) == EXIT_SUCCESS
        puts = [r for r in server.state.recordings if r.method == "PUT"]
        assert len(puts) == 1


def test_result_persist_failure_exit_seven(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plan = build_governance_plan(create_config(), empty_remote())
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(plan.to_canonical_json(), encoding="utf-8")
    result_path = tmp_path / "result.json"

    import purview_governance.cli as cli_mod

    def boom(*_args, **_kwargs):
        raise cli_mod._CliLocalError("cli.result_persist_failed")

    monkeypatch.setattr(cli_mod, "_write_atomic", boom)

    with start_contract_server(list_mode="empty", put_mode="created") as server:

        def factory(endpoint: str):
            return make_loopback_client(server.base_url, logical_target_endpoint=endpoint)

        code = _run(
            ["apply", str(plan_path), "--apply", "--result", str(result_path), "--json"],
            deps=_CliDependencies(scanning_client_factory=factory),
        )
        assert code == EXIT_PERSIST
        assert len([r for r in server.state.recordings if r.method == "PUT"]) == 1


def test_output_directory_rejected_pre_network(tmp_path: Path) -> None:
    plan = build_governance_plan(create_config(), empty_remote())
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(plan.to_canonical_json(), encoding="utf-8")
    out_dir = tmp_path / "outdir"
    out_dir.mkdir()

    with start_contract_server(list_mode="empty") as server:

        def factory(endpoint: str):
            return make_loopback_client(server.base_url, logical_target_endpoint=endpoint)

        deps = _CliDependencies(scanning_client_factory=factory)
        code = _run(
            ["apply", str(plan_path), "--apply", "--result", str(out_dir), "--force"],
            deps=deps,
        )
        assert code == EXIT_VALIDATION
        assert server.state.recordings == []

        config_path = tmp_path / "cfg.yaml"
        config_path.write_text(EMPTY_CONFIG_YAML, encoding="utf-8")
        code = _run(
            ["plan", "create", str(config_path), "--output", str(out_dir), "--force"],
            deps=deps,
        )
        assert code == EXIT_VALIDATION
        assert server.state.recordings == []

        code = _run(
            [
                "remote-state",
                "capture",
                str(config_path),
                "--output",
                str(out_dir),
                "--force",
            ],
            deps=deps,
        )
        assert code == EXIT_VALIDATION
        assert server.state.recordings == []


def test_unexpected_apply_exception_exit_codes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    plan = build_governance_plan(create_config(), empty_remote())
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(plan.to_canonical_json(), encoding="utf-8")

    import purview_governance.cli as cli_mod

    def boom(*_args, **_kwargs):
        raise RuntimeError("SECRET_SENTINEL_apply_boom")

    monkeypatch.setattr(cli_mod, "execute_governance_plan", boom)

    with start_contract_server(list_mode="empty") as server:

        def factory(endpoint: str):
            return make_loopback_client(server.base_url, logical_target_endpoint=endpoint)

        deps = _CliDependencies(scanning_client_factory=factory)
        dry = _run(["apply", str(plan_path)], deps=deps)
        err = capsys.readouterr().err
        assert dry == EXIT_PREWRITE
        assert "cli.apply_failed" in err
        assert "SECRET_SENTINEL_apply_boom" not in err
        assert "Traceback" not in err

        apply_code = _run(["apply", str(plan_path), "--apply"], deps=deps)
        err2 = capsys.readouterr().err
        assert apply_code == EXIT_WRITE
        assert "cli.apply_internal_failure" in err2
        assert "SECRET_SENTINEL_apply_boom" not in err2
        assert "Traceback" not in err2
        assert server.state.recordings == []


def test_blocked_plan_exit_safety(tmp_path: Path) -> None:
    from purview_governance.remote_state.models import build_remote_state
    from tests.plan.helpers import remote_ds

    remote = build_remote_state((remote_ds(creation_type="AutoNative"),), ())
    plan = build_governance_plan(create_config(), remote)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(plan.to_canonical_json(), encoding="utf-8")
    with start_contract_server(list_mode="empty") as server:

        def factory(endpoint: str):
            return make_loopback_client(server.base_url, logical_target_endpoint=endpoint)

        code = _run(
            ["apply", str(plan_path)],
            deps=_CliDependencies(scanning_client_factory=factory),
        )
    assert code == EXIT_SAFETY
    assert server.state.recordings == []
