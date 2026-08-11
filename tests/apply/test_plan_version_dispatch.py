"""Apply plan/v2 acceptance and unsupported-version fail-closed."""

from __future__ import annotations

import pytest

from purview_governance.apply import (
    ApplyValidationError,
    ExecutionMode,
    execute_governance_plan,
)
from purview_governance.apply.identity import RESULT_API_VERSION_V2
from purview_governance.config import validate_config_text
from purview_governance.plan import build_governance_plan, build_governance_plan_v2
from purview_governance.remote_state import capture_remote_state_v2
from tests.contract.client_helpers import make_loopback_client
from tests.contract.server import start_contract_server
from tests.plan.helpers import create_config, empty_remote

_EMPTY_V2 = """
apiVersion: purview-governance-config/v2
target:
  endpoint: https://account.purview.azure.com
authentication:
  strategy: defaultAzureCredential
resources: []
"""


def test_plan_v1_still_applies_dry_run() -> None:
    plan = build_governance_plan(create_config(), empty_remote())
    with (
        start_contract_server(list_mode="empty") as server,
        make_loopback_client(server.base_url) as client,
    ):
        result = execute_governance_plan(plan, client)
    assert result.status == "dry-run-ready"
    assert result.writes_attempted == 0
    assert result.api_version == "purview-execution-result/v1"


def test_plan_v2_dry_run_accepted_zero_puts() -> None:
    config = validate_config_text(_EMPTY_V2, format_hint="yaml")
    with (
        start_contract_server(list_mode="empty") as server,
        make_loopback_client(server.base_url) as client,
    ):
        remote = capture_remote_state_v2(client)
        plan = build_governance_plan_v2(config, remote)
        result = execute_governance_plan(plan, client, mode=ExecutionMode.DRY_RUN)
        assert result.status == "dry-run-ready"
        assert result.api_version == RESULT_API_VERSION_V2
        assert result.writes_attempted == 0
        assert not any(r.method == "PUT" for r in server.state.recordings)


def test_unsupported_plan_version_rejected_before_network() -> None:
    plan = build_governance_plan(create_config(), empty_remote())
    object.__setattr__(plan, "api_version", "purview-governance-plan/v9")
    with (
        start_contract_server(list_mode="empty") as server,
        make_loopback_client(server.base_url) as client,
    ):
        with pytest.raises(ApplyValidationError) as exc:
            execute_governance_plan(plan, client)
        assert exc.value.code == "apply.unsupported_plan_version"
        assert server.state.recordings == []
