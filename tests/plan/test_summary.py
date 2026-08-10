"""Human summary rendering."""

from __future__ import annotations

from purview_governance.plan import build_governance_plan, format_plan_summary
from tests.plan.helpers import create_config, empty_remote


def test_format_plan_summary_deterministic() -> None:
    plan = build_governance_plan(create_config(), empty_remote())
    a = format_plan_summary(plan)
    b = format_plan_summary(plan)
    assert a == b
    assert a.endswith("\n")
    assert "planIdentity:" in a
    assert "executionEligibility: ready" in a
    assert "1. create dataSource/example-source" in a
