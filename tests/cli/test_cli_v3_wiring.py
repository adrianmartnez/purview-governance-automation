"""Unit tests for CLI Unified Catalog (v3) wiring helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from purview_governance.cli import (
    EXIT_SAFETY,
    EXIT_VALIDATION,
    _CliDependencies,
    _config_validation_error_code,
    _run,
)
from purview_governance.config.diagnostics import ConfigDiagnostic, ConfigValidationError
from purview_governance.unified_catalog.client import PurviewUnifiedCatalogClient
from tests.apply.helpers_v3 import apply_server
from tests.apply.test_blocked_short_circuit_v3 import _blocked_plan_and_remote


def test_config_validation_error_code_uses_first_diagnostic() -> None:
    exc = ConfigValidationError(
        (
            ConfigDiagnostic(code="config.unknown_field", path="/z", message="z"),
            ConfigDiagnostic(code="config.invalid_syntax", path="/a", message="a"),
        )
    )
    # diagnostics are sorted by (path, code, message) → /a first
    assert _config_validation_error_code(exc) == "config.invalid_syntax"


def test_config_validation_error_code_fallback_when_empty() -> None:
    exc = ConfigValidationError(())
    assert _config_validation_error_code(exc) == "cli.config_invalid"


def test_v1_apply_rejects_credential_flag_without_secrets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from purview_governance.plan import build_governance_plan
    from tests.plan.helpers import create_config, empty_remote

    monkeypatch.setenv("AZURE_CLIENT_SECRET", "must-not-be-read")
    plan = build_governance_plan(create_config(), empty_remote())
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(plan.to_canonical_json(), encoding="utf-8")

    code = _run(
        ["apply", str(plan_path), "--credential", "client-secret"],
    )
    assert code == EXIT_VALIDATION
    assert "cli.credential_flag_unsupported" in capsys.readouterr().err


def test_blocked_apply_v3_without_credential_exits_safety(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    plan, remote = _blocked_plan_and_remote()
    assert plan.execution_eligibility == "blocked"

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
    assert '"status":"blocked"' in capsys.readouterr().out.replace(" ", "")
