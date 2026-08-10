"""Official plan serializer self-validation boundary."""

from __future__ import annotations

import pytest

from purview_governance.desired.models import DesiredState
from purview_governance.diff.models import DiffDocument, DiffItem
from purview_governance.plan import (
    GovernancePlan,
    PlanError,
    PlanIdentities,
    PlanSummary,
    PlanTargetContext,
    build_governance_plan,
)
from purview_governance.plan.identity import CONFIGURATION_API_VERSION, PLAN_API_VERSION
from tests.plan.helpers import create_config, empty_remote


def test_manual_inconsistent_plan_cannot_serialize() -> None:
    plan = GovernancePlan(
        api_version=PLAN_API_VERSION,
        configuration_api_version=CONFIGURATION_API_VERSION,
        target_context=PlanTargetContext(
            endpoint="https://account.purview.azure.com",
            identity="sha256:" + ("a" * 64),
        ),
        identities=PlanIdentities(
            material_configuration="sha256:" + ("b" * 64),
            desired_state="sha256:" + ("c" * 64),
            remote_state="sha256:" + ("d" * 64),
        ),
        desired_state=DesiredState(data_sources=()),
        change_set=DiffDocument(
            items=(
                DiffItem(
                    name="ghost-source",
                    resource_type="dataSource",
                    outcome="no-op",
                    reasons=(),
                ),
            )
        ),
        execution_eligibility="ready",
        operations=(),
        summary=PlanSummary(
            total=1,
            create=0,
            replace=0,
            no_op=1,
            remote_only=0,
            blocked=0,
            operations=0,
        ),
        plan_identity="sha256:" + ("e" * 64),
    )
    with pytest.raises(PlanError):
        plan.to_canonical_json()


def test_builder_plan_serializes() -> None:
    plan = build_governance_plan(create_config(), empty_remote())
    text = plan.to_canonical_json()
    assert text.startswith("{")
    assert "planIdentity" in text
