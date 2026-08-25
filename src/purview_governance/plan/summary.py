"""Deterministic human-inspectable plan summary rendering."""

from __future__ import annotations

from purview_governance.diff.models_v3 import (
    DiffBusinessDomainItem,
    DiffDataProductItem,
    DiffGlossaryTermItem,
)
from purview_governance.plan.models import GovernancePlan
from purview_governance.plan.models_v3 import GovernancePlanV3, PlanTargetContextV3


def format_plan_summary(plan: GovernancePlan | GovernancePlanV3) -> str:
    """Return a deterministic plain-text summary for reviewers (no ANSI/timestamps)."""
    target = plan.target_context
    lines: list[str] = [
        f"apiVersion: {plan.api_version}",
        f"executionEligibility: {plan.execution_eligibility}",
        f"planIdentity: {plan.plan_identity}",
    ]
    if isinstance(target, PlanTargetContextV3):
        lines.extend(
            [
                f"targetContext.surface: {target.surface}",
                f"targetContext.tenantId: {target.tenant_id}",
                f"targetContext.endpoint: {target.endpoint}",
                f"targetContext.identity: {target.identity}",
            ]
        )
    else:
        lines.extend(
            [
                f"targetContext.endpoint: {target.endpoint}",
                f"targetContext.identity: {target.identity}",
            ]
        )
    lines.extend(
        [
            f"identities.materialConfiguration: {plan.identities.material_configuration}",
            f"identities.desiredState: {plan.identities.desired_state}",
            f"identities.remoteState: {plan.identities.remote_state}",
            (
                "summary: "
                f"total={plan.summary.total} "
                f"create={plan.summary.create} "
                f"replace={plan.summary.replace} "
                f"noOp={plan.summary.no_op} "
                f"remoteOnly={plan.summary.remote_only} "
                f"blocked={plan.summary.blocked} "
                f"operations={plan.summary.operations}"
            ),
            "operations:",
        ]
    )
    if not plan.operations:
        lines.append("  (none)")
    else:
        for operation in plan.operations:
            resource_key = operation.id if isinstance(plan, GovernancePlanV3) else operation.name
            lines.append(
                f"  {operation.sequence}. {operation.action} "
                f"{operation.resource_type}/{resource_key}"
            )

    lines.append("blockedFindings:")
    blocked = [item for item in plan.change_set.items if item.outcome == "blocked"]
    if not blocked:
        lines.append("  (none)")
    else:
        for item in blocked:
            reason_codes = ",".join(reason.code for reason in item.reasons)
            lines.append(f"  {_change_item_label(item)}: {reason_codes}")

    if plan.execution_eligibility == "blocked":
        lines.append("note: executionEligibility=blocked requires ZERO WRITES on apply")
    return "\n".join(lines) + "\n"


def _change_item_label(item: object) -> str:
    if isinstance(item, (DiffBusinessDomainItem, DiffDataProductItem, DiffGlossaryTermItem)):
        return item.id
    name = getattr(item, "name", None)
    if isinstance(name, str):
        return name
    item_id = getattr(item, "id", None)
    if isinstance(item_id, str):
        return item_id
    return "?"
