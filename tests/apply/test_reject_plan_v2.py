"""Apply must reject plan/v2 before any network activity."""

from __future__ import annotations

import pytest

from purview_governance.apply import ApplyValidationError, execute_governance_plan
from purview_governance.desired.models import DesiredState
from purview_governance.diff.models import DiffDocument
from purview_governance.plan import build_governance_plan
from purview_governance.plan.identity import (
    PLAN_API_VERSION_V2,
    compute_desired_state_identity,
    compute_material_configuration_identity,
    compute_plan_identity,
    compute_target_context_identity,
)
from purview_governance.plan.models import (
    GovernancePlan,
    PlanIdentities,
    PlanSummary,
    PlanTargetContext,
)
from tests.contract.client_helpers import make_loopback_client
from tests.contract.server import start_contract_server
from tests.plan.helpers import create_config, empty_remote


class _RecordingClient:
    """Minimal client stand-in that records whether PUT was attempted."""

    def __init__(self, inner) -> None:
        self._inner = inner
        self.put_calls: list[tuple[str, object]] = []
        self.target_endpoint = inner.target_endpoint

    def __getattr__(self, name: str):
        return getattr(self._inner, name)

    def _create_or_replace_data_source(self, name: str, payload: object):
        self.put_calls.append((name, payload))
        return self._inner._create_or_replace_data_source(name, payload)


def _minimal_plan_v2() -> GovernancePlan:
    endpoint = "https://account.purview.azure.com"
    target_identity = compute_target_context_identity(endpoint)
    desired = DesiredState(data_sources=())
    desired_doc = desired.to_document(multi_resource=True)
    desired_identity = compute_desired_state_identity(desired_doc)
    material = compute_material_configuration_identity(
        target_context_identity=target_identity,
        desired_state_identity=desired_identity,
        configuration_api_version="purview-governance-config/v2",
    )
    remote_identity = "sha256:" + ("b" * 64)
    without_identity = {
        "apiVersion": PLAN_API_VERSION_V2,
        "changeSet": {"items": []},
        "configurationApiVersion": "purview-governance-config/v2",
        "desiredState": desired_doc,
        "executionEligibility": "ready",
        "identities": {
            "desiredState": desired_identity,
            "materialConfiguration": material,
            "remoteState": remote_identity,
        },
        "operations": [],
        "summary": {
            "blocked": 0,
            "create": 0,
            "noOp": 0,
            "operations": 0,
            "remoteOnly": 0,
            "replace": 0,
            "total": 0,
        },
        "targetContext": {"endpoint": endpoint, "identity": target_identity},
    }
    plan_identity = compute_plan_identity(without_identity)
    return GovernancePlan(
        api_version=PLAN_API_VERSION_V2,
        configuration_api_version="purview-governance-config/v2",
        target_context=PlanTargetContext(endpoint=endpoint, identity=target_identity),
        identities=PlanIdentities(
            material_configuration=material,
            desired_state=desired_identity,
            remote_state=remote_identity,
        ),
        desired_state=desired,
        change_set=DiffDocument(items=()),
        execution_eligibility="ready",
        operations=(),
        summary=PlanSummary(
            total=0,
            create=0,
            replace=0,
            no_op=0,
            remote_only=0,
            blocked=0,
            operations=0,
        ),
        plan_identity=plan_identity,
    )


def test_plan_v1_still_applies_dry_run() -> None:
    plan = build_governance_plan(create_config(), empty_remote())
    with (
        start_contract_server(list_mode="empty") as server,
        make_loopback_client(server.base_url) as client,
    ):
        result = execute_governance_plan(plan, client)
    assert result.status == "dry-run-ready"
    assert result.writes_attempted == 0


def test_plan_v2_rejected_before_put() -> None:
    plan = _minimal_plan_v2()
    with (
        start_contract_server(list_mode="empty") as server,
        make_loopback_client(server.base_url) as client,
    ):
        recording = _RecordingClient(client)
        with pytest.raises(ApplyValidationError) as exc:
            execute_governance_plan(plan, recording)  # type: ignore[arg-type]
        assert exc.value.code == "apply.unsupported_plan_version"
        assert recording.put_calls == []
        assert server.state.recordings == []
