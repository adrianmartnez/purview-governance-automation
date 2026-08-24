"""Offline governance plan builder for Business Domains (v3)."""

from __future__ import annotations

from purview_governance.config.models_v3 import (
    CONFIG_API_VERSION_V3,
    MAX_BUSINESS_DOMAINS,
    MAX_HIERARCHY_DEPTH,
    UNIFIED_CATALOG_SURFACE,
    GovernanceConfigV3,
)
from purview_governance.desired.mapping_v3 import desired_state_from_config_v3
from purview_governance.diff.business_domain import diff_desired_vs_remote_v3
from purview_governance.diff.models_v3 import DiffBusinessDomainItem
from purview_governance.plan.errors import PlanBuildError, PlanError
from purview_governance.plan.identity import (
    CONFIGURATION_API_VERSION_V3,
    compute_desired_state_identity,
    compute_material_configuration_identity,
    compute_target_context_identity_v3,
)
from purview_governance.plan.models_v3 import (
    GovernancePlanV3,
    PlanIdentities,
    PlanOperationV3,
    PlanSummary,
    PlanTargetContextV3,
    build_plan_from_parts_v3,
)
from purview_governance.plan.validation_v3 import (
    validate_governance_config_for_planning_v3,
    validate_plan_document_for_serialization_v3,
    validate_remote_state_for_planning_v3,
)
from purview_governance.remote_state.models_v3 import RemoteStateV3, remote_observed_count_v3


def _summarize_change_set(change_set) -> dict[str, int]:
    counts = {
        "create": 0,
        "replace": 0,
        "no-op": 0,
        "remote-only": 0,
        "blocked": 0,
    }
    for item in change_set.items:
        counts[item.outcome] += 1
    return counts


def _business_domain_items(change_set) -> list[DiffBusinessDomainItem]:
    return [item for item in change_set.items if isinstance(item, DiffBusinessDomainItem)]


def _topological_create_order(
    desired_ids: set[str],
    parent_by_id: dict[str, str | None],
    create_ids: list[str],
) -> list[str]:
    """Return create ids ordered so parents appear before children."""
    create_set = set(create_ids)
    ordered: list[str] = []
    placed: set[str] = set()

    def can_place(domain_id: str) -> bool:
        parent = parent_by_id.get(domain_id)
        if parent is None:
            return True
        if parent in create_set:
            return parent in placed
        return True

    remaining = list(create_ids)
    while remaining:
        progress = False
        next_remaining: list[str] = []
        for domain_id in remaining:
            if can_place(domain_id):
                ordered.append(domain_id)
                placed.add(domain_id)
                progress = True
            else:
                next_remaining.append(domain_id)
        if not progress:
            raise PlanBuildError(
                "plan.hierarchy_cycle",
                "Business Domain create ordering failed due to a parent cycle",
            )
        remaining = next_remaining
    return ordered


def _all_domain_ids(remote: RemoteStateV3, desired_ids: set[str]) -> set[str]:
    ids = set(desired_ids)
    for domain in remote.business_domains:
        ids.add(domain.id)
    for item in remote.uninterpreted_business_domains:
        if item.id is not None:
            ids.add(item.id)
    return ids


def _validate_resolved_parents(
    parent_by_id: dict[str, str | None],
    all_ids: set[str],
) -> None:
    for domain_id, parent_id in parent_by_id.items():
        if parent_id is None:
            continue
        if parent_id not in all_ids:
            raise PlanBuildError(
                "plan.hierarchy_ambiguous",
                (f"Business Domain {domain_id!r} references unresolved parentId {parent_id!r}"),
            )


def _compute_hierarchy_depth(
    parent_by_id: dict[str, str | None],
    domain_id: str,
    all_ids: set[str],
) -> int:
    depth = 0
    current: str | None = domain_id
    visited: set[str] = set()
    while current is not None:
        if current in visited:
            raise PlanBuildError(
                "plan.hierarchy_cycle",
                "Business Domain hierarchy contains a cycle",
            )
        visited.add(current)
        depth += 1
        parent = parent_by_id.get(current)
        if parent is None:
            break
        if parent not in all_ids:
            raise PlanBuildError(
                "plan.hierarchy_ambiguous",
                (f"Business Domain {current!r} references unresolved parentId {parent!r}"),
            )
        current = parent
    return depth


def _build_resultant_parent_map(
    desired: dict[str, str | None],
    remote: RemoteStateV3,
    desired_ids: set[str],
) -> dict[str, str | None]:
    parent_by_id: dict[str, str | None] = {}
    for domain in remote.business_domains:
        props = domain.properties
        parent_by_id[domain.id] = props.get("parentId")
    for domain_id, parent_id in desired.items():
        parent_by_id[domain_id] = parent_id
    return parent_by_id


def build_governance_plan_v3(
    config: GovernanceConfigV3,
    remote: RemoteStateV3,
) -> GovernancePlanV3:
    """Build a deterministic purview-governance-plan/v3 from config + remote state."""
    if config.api_version != CONFIG_API_VERSION_V3:
        raise PlanBuildError(
            "plan.requires_v3_builder",
            "config apiVersion requires build_governance_plan_v3",
        )

    validate_governance_config_for_planning_v3(config)
    validate_remote_state_for_planning_v3(remote)

    if config.target.tenant_id != remote.target_context.tenant_id:
        raise PlanBuildError(
            "plan.target_mismatch",
            "configuration tenantId must match remote targetContext.tenantId",
        )

    desired = desired_state_from_config_v3(config)
    change_set = diff_desired_vs_remote_v3(desired, remote)

    normalized_endpoint = remote.target_context.endpoint
    target_identity = compute_target_context_identity_v3(
        surface=UNIFIED_CATALOG_SURFACE,
        tenant_id=config.target.tenant_id,
        endpoint=normalized_endpoint,
    )
    desired_identity = compute_desired_state_identity(desired.to_document())
    material_identity = compute_material_configuration_identity(
        target_context_identity=target_identity,
        desired_state_identity=desired_identity,
        configuration_api_version=CONFIGURATION_API_VERSION_V3,
    )

    counts = _summarize_change_set(change_set)
    items = _business_domain_items(change_set)

    parent_by_desired = {domain.id: domain.parent_id for domain in desired.business_domains}
    desired_ids = set(parent_by_desired.keys())

    create_ids = [item.id for item in items if item.outcome == "create"]
    replace_ids = sorted(item.id for item in items if item.outcome == "replace")

    eligible_creates = len(create_ids)
    observed = remote_observed_count_v3(remote)
    if observed + eligible_creates > MAX_BUSINESS_DOMAINS:
        raise PlanBuildError(
            "plan.business_domain_count_exceeded",
            f"resultant Business Domain count would exceed {MAX_BUSINESS_DOMAINS}",
        )

    parent_map = _build_resultant_parent_map(parent_by_desired, remote, desired_ids)
    all_ids = _all_domain_ids(remote, desired_ids)
    _validate_resolved_parents(parent_map, all_ids)
    max_depth = 0
    for domain_id in parent_map:
        depth = _compute_hierarchy_depth(parent_map, domain_id, all_ids)
        max_depth = max(max_depth, depth)
    if max_depth > MAX_HIERARCHY_DEPTH:
        raise PlanBuildError(
            "plan.hierarchy_depth_exceeded",
            f"resultant Business Domain hierarchy depth exceeds {MAX_HIERARCHY_DEPTH}",
        )

    ordered_creates = _topological_create_order(desired_ids, parent_by_desired, create_ids)
    operations_list: list[PlanOperationV3] = []
    sequence = 1
    for domain_id in ordered_creates:
        operations_list.append(
            PlanOperationV3(
                sequence=sequence,
                resource_type="businessDomain",
                id=domain_id,
                action="create",
            )
        )
        sequence += 1
    for domain_id in replace_ids:
        item = next(item for item in items if item.id == domain_id)
        if any(reason.code == "remote.unsupported_configurable_field" for reason in item.reasons):
            continue
        operations_list.append(
            PlanOperationV3(
                sequence=sequence,
                resource_type="businessDomain",
                id=domain_id,
                action="replace",
            )
        )
        sequence += 1

    eligibility = "blocked" if counts["blocked"] > 0 else "ready"
    summary = PlanSummary(
        total=len(items),
        create=counts["create"],
        replace=counts["replace"],
        no_op=counts["no-op"],
        remote_only=counts["remote-only"],
        blocked=counts["blocked"],
        operations=len(operations_list),
    )

    plan = build_plan_from_parts_v3(
        target_context=PlanTargetContextV3(
            surface=UNIFIED_CATALOG_SURFACE,
            tenant_id=config.target.tenant_id,
            endpoint=normalized_endpoint,
            identity=target_identity,
        ),
        identities=PlanIdentities(
            material_configuration=material_identity,
            desired_state=desired_identity,
            remote_state=remote.material_state_identity,
        ),
        desired_state=desired,
        change_set=change_set,
        execution_eligibility=eligibility,  # type: ignore[arg-type]
        operations=tuple(operations_list),
        summary=summary,
    )

    self_validate_failed = False
    try:
        validate_plan_document_for_serialization_v3(plan.to_document())
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
