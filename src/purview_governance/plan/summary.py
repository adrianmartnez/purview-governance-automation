"""Deterministic human-inspectable plan summary rendering."""

from __future__ import annotations

from purview_governance.plan.models import GovernancePlan


def format_plan_summary(plan: GovernancePlan) -> str:
    """Return a deterministic plain-text summary for reviewers (no ANSI/timestamps)."""
    lines: list[str] = [
        f"apiVersion: {plan.api_version}",
        f"executionEligibility: {plan.execution_eligibility}",
        f"planIdentity: {plan.plan_identity}",
        f"targetContext.endpoint: {plan.target_context.endpoint}",
        f"targetContext.identity: {plan.target_context.identity}",
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
    if not plan.operations:
        lines.append("  (none)")
    else:
        for operation in plan.operations:
            lines.append(
                f"  {operation.sequence}. {operation.action} "
                f"{operation.resource_type}/{operation.name}"
            )

    lines.append("blockedFindings:")
    blocked = [item for item in plan.change_set.items if item.outcome == "blocked"]
    if not blocked:
        lines.append("  (none)")
    else:
        for item in blocked:
            reason_codes = ",".join(reason.code for reason in item.reasons)
            lines.append(f"  {item.name}: {reason_codes}")

    if plan.execution_eligibility == "blocked":
        lines.append("note: executionEligibility=blocked requires ZERO WRITES on apply (#15)")
    return "\n".join(lines) + "\n"
