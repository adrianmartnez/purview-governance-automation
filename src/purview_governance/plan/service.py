"""Read-only offline governance plan builder."""

from __future__ import annotations

from purview_governance.config.models import GovernanceConfig
from purview_governance.desired.mapping import desired_state_from_config
from purview_governance.diff.service import diff_desired_vs_remote
from purview_governance.plan.errors import PlanBuildError, PlanError
from purview_governance.plan.identity import (
    compute_desired_state_identity,
    compute_material_configuration_identity,
    compute_target_context_identity,
)
from purview_governance.plan.models import (
    GovernancePlan,
    PlanIdentities,
    PlanOperation,
    PlanSummary,
    PlanTargetContext,
    build_plan_from_parts,
)
from purview_governance.plan.validation import (
    validate_governance_config_for_planning,
    validate_plan_document_for_serialization,
    validate_remote_state_for_planning,
)
from purview_governance.remote_state.models import RemoteState


def build_governance_plan(
    config: GovernanceConfig,
    remote_state: RemoteState,
) -> GovernancePlan:
    """Build a deterministic purview-governance-plan/v1 from config + remote state.

    Pure/offline: derives desired and diff internally. Performs zero remote writes.
    A plan with ``executionEligibility=blocked`` must produce zero writes in apply (#15).
    """
    normalized_endpoint = validate_governance_config_for_planning(config)
    validate_remote_state_for_planning(remote_state)

    desired = desired_state_from_config(config)
    # Explicit kind gate already enforced; mapping still hardcodes AzureStorage by design.
    for resource in config.resources:
        if resource.kind != "AzureStorage":
            raise PlanBuildError(
                "plan.invalid_configuration_input",
                "data source kind must be AzureStorage",
            )

    change_set = diff_desired_vs_remote(desired, remote_state)

    target_identity = compute_target_context_identity(normalized_endpoint)
    desired_identity = compute_desired_state_identity(desired.to_document())
    material_identity = compute_material_configuration_identity(
        target_context_identity=target_identity,
        desired_state_identity=desired_identity,
    )

    create_replace: list[tuple[str, str]] = []
    counts = {
        "create": 0,
        "replace": 0,
        "no-op": 0,
        "remote-only": 0,
        "blocked": 0,
    }
    for item in change_set.items:
        counts[item.outcome] += 1
        if item.outcome in {"create", "replace"}:
            create_replace.append((item.outcome, item.name))

    create_replace.sort(key=lambda pair: pair[1])
    operations = tuple(
        PlanOperation(
            sequence=index,
            resource_type="dataSource",
            name=name,
            action=action,  # type: ignore[arg-type]
        )
        for index, (action, name) in enumerate(create_replace, start=1)
    )

    eligibility = "blocked" if counts["blocked"] > 0 else "ready"
    summary = PlanSummary(
        total=len(change_set.items),
        create=counts["create"],
        replace=counts["replace"],
        no_op=counts["no-op"],
        remote_only=counts["remote-only"],
        blocked=counts["blocked"],
        operations=len(operations),
    )

    plan = build_plan_from_parts(
        target_context=PlanTargetContext(
            endpoint=normalized_endpoint,
            identity=target_identity,
        ),
        identities=PlanIdentities(
            material_configuration=material_identity,
            desired_state=desired_identity,
            remote_state=remote_state.material_state_identity,
        ),
        desired_state=desired,
        change_set=change_set,
        execution_eligibility=eligibility,  # type: ignore[arg-type]
        operations=operations,
        summary=summary,
    )

    self_validate_failed = False
    try:
        validate_plan_document_for_serialization(plan.to_document())
    except PlanError:
        self_validate_failed = True
    except Exception:
        self_validate_failed = True
    if self_validate_failed:
        raise PlanBuildError(
            "plan.invalid_schema",
            "generated plan failed self-validation",
        )
    return plan
