"""Versioned deterministic governance plan artifacts (purview-governance-plan/v1–/v3)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from purview_governance.plan.errors import (
    PlanBuildError,
    PlanError,
    PlanIntegrityError,
    PlanLoadError,
    PlanSchemaError,
    PlanVersionError,
)
from purview_governance.plan.identity import (
    CONFIGURATION_API_VERSION_V3,
    PLAN_API_VERSION,
    PLAN_API_VERSION_V2,
    PLAN_API_VERSION_V3,
)
from purview_governance.plan.schema import (
    load_plan_v1_schema,
    load_plan_v2_schema,
    load_plan_v3_schema,
)

if TYPE_CHECKING:
    from purview_governance.plan.models import (
        GovernancePlan,
        PlanIdentities,
        PlanOperation,
        PlanSummary,
        PlanTargetContext,
    )
    from purview_governance.plan.models_v3 import (
        GovernancePlanV3,
        PlanOperationV3,
        PlanTargetContextV3,
    )

_LAZY_EXPORTS = {
    "GovernancePlan": "purview_governance.plan.models",
    "PlanIdentities": "purview_governance.plan.models",
    "PlanOperation": "purview_governance.plan.models",
    "PlanSummary": "purview_governance.plan.models",
    "PlanTargetContext": "purview_governance.plan.models",
    "GovernancePlanV3": "purview_governance.plan.models_v3",
    "PlanOperationV3": "purview_governance.plan.models_v3",
    "PlanTargetContextV3": "purview_governance.plan.models_v3",
    "build_governance_plan": "purview_governance.plan.service",
    "build_governance_plan_v2": "purview_governance.plan.service",
    "build_governance_plan_v3": "purview_governance.plan.service_v3",
    "format_plan_summary": "purview_governance.plan.summary",
    "load_plan_file": "purview_governance.plan.loader",
    "load_plan_text": "purview_governance.plan.loader",
    "load_plan_v3_file": "purview_governance.plan.loader",
    "load_plan_v3_text": "purview_governance.plan.loader",
}


def __getattr__(name: str) -> object:
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name = _LAZY_EXPORTS[name]
    import importlib

    module = importlib.import_module(module_name)
    return getattr(module, name)


__all__ = [
    "CONFIGURATION_API_VERSION_V3",
    "PLAN_API_VERSION",
    "PLAN_API_VERSION_V2",
    "PLAN_API_VERSION_V3",
    "GovernancePlan",
    "GovernancePlanV3",
    "PlanBuildError",
    "PlanError",
    "PlanIdentities",
    "PlanIntegrityError",
    "PlanLoadError",
    "PlanOperation",
    "PlanOperationV3",
    "PlanSchemaError",
    "PlanSummary",
    "PlanTargetContext",
    "PlanTargetContextV3",
    "PlanVersionError",
    "build_governance_plan",
    "build_governance_plan_v2",
    "build_governance_plan_v3",
    "format_plan_summary",
    "load_plan_file",
    "load_plan_text",
    "load_plan_v3_file",
    "load_plan_v3_text",
    "load_plan_v1_schema",
    "load_plan_v2_schema",
    "load_plan_v3_schema",
]
