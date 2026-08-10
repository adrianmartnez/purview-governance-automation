"""Determinism and isolation smoke for plan package."""

from __future__ import annotations

import purview_governance.plan as plan_pkg
from purview_governance.plan import build_governance_plan
from tests.plan.helpers import create_config, empty_remote


def test_plan_package_has_no_scanning_or_auth_imports() -> None:
    module_names = set(plan_pkg.__dict__)
    # Public surface should not re-export scanning/auth mutation primitives.
    assert "PurviewScanningClient" not in module_names
    assert "TokenCredential" not in dir(plan_pkg)


def test_build_is_offline_pure() -> None:
    plan_a = build_governance_plan(create_config(), empty_remote())
    plan_b = build_governance_plan(create_config(), empty_remote())
    assert plan_a.to_canonical_json() == plan_b.to_canonical_json()
