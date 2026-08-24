"""Offline governance plan builder for Unified Catalog (v3)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from purview_governance.config.models_v3 import (
    CONFIG_API_VERSION_V3,
    MAX_BUSINESS_DOMAINS,
    MAX_HIERARCHY_DEPTH,
    UNIFIED_CATALOG_SURFACE,
    GovernanceConfigV3,
)
from purview_governance.desired.mapping_v3 import desired_state_from_config_v3
from purview_governance.desired.models_v3 import DataProductDesiredState
from purview_governance.diff.business_domain import diff_desired_vs_remote_v3
from purview_governance.diff.models import DiffDocument
from purview_governance.diff.models_v3 import (
    DiffBusinessDomainItem,
    DiffDataProductItem,
    DiffGlossaryTermItem,
)
from purview_governance.plan.errors import PlanBuildError, PlanError
from purview_governance.plan.glossary_term_v3 import enforce_glossary_term_dependencies
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


@dataclass(frozen=True, slots=True)
class _DomainResolution:
    status: Literal["satisfied", "depends_on_create", "blocked"]
    reason_code: str | None = None


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


def _data_product_items(change_set) -> list[DiffDataProductItem]:
    return [item for item in change_set.items if isinstance(item, DiffDataProductItem)]


def _glossary_term_items(change_set) -> list[DiffGlossaryTermItem]:
    return [item for item in change_set.items if isinstance(item, DiffGlossaryTermItem)]


def _change_set_sort_key(item) -> tuple[int, str]:
    if item.resource_type == "businessDomain":
        rank = 0
    elif item.resource_type == "dataProduct":
        rank = 1
    else:
        rank = 2
    return (rank, item.id)


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
) -> dict[str, str | None]:
    parent_by_id: dict[str, str | None] = {}
    for domain in remote.business_domains:
        props = domain.properties
        parent_by_id[domain.id] = props.get("parentId")
    for domain_id, parent_id in desired.items():
        parent_by_id[domain_id] = parent_id
    return parent_by_id


def _normalized_domain_ids(remote: RemoteStateV3) -> set[str]:
    return {domain.id for domain in remote.business_domains}


def _uninterpreted_domain_ids(remote: RemoteStateV3) -> set[str]:
    return {item.id for item in remote.uninterpreted_business_domains if item.id is not None}


def _desired_domain_ids(config: GovernanceConfigV3) -> set[str]:
    from purview_governance.config.models_v3 import BusinessDomainResourceConfig

    return {
        resource.id
        for resource in config.resources
        if isinstance(resource, BusinessDomainResourceConfig)
    }


def _bd_create_eligible(change_set, domain_id: str) -> bool:
    for item in change_set.items:
        if isinstance(item, DiffBusinessDomainItem) and item.id == domain_id:
            return item.outcome == "create"
    return False


def _bd_create_blocked(change_set, domain_id: str) -> bool:
    for item in change_set.items:
        if isinstance(item, DiffBusinessDomainItem) and item.id == domain_id:
            return item.outcome == "blocked"
    return False


def _resolve_domain(
    domain_id: str,
    *,
    remote: RemoteStateV3,
    change_set,
    desired_domain_ids: set[str],
) -> _DomainResolution:
    if domain_id in _normalized_domain_ids(remote):
        return _DomainResolution(status="satisfied")
    if domain_id in _uninterpreted_domain_ids(remote):
        return _DomainResolution(status="blocked", reason_code="plan.domain_uninterpreted")
    if domain_id in desired_domain_ids:
        if _bd_create_eligible(change_set, domain_id):
            return _DomainResolution(status="depends_on_create")
        if _bd_create_blocked(change_set, domain_id):
            return _DomainResolution(status="blocked", reason_code="plan.domain_dependency_blocked")
        return _DomainResolution(status="blocked", reason_code="plan.domain_unresolved")
    return _DomainResolution(status="blocked", reason_code="plan.domain_unresolved")


def _block_data_product_for_domain(
    item: DiffDataProductItem,
    *,
    reason_code: str,
) -> DiffDataProductItem:
    from purview_governance.diff.reasons import reason, sort_reasons

    reasons = list(item.reasons)
    reasons.append(reason(reason_code, "/properties/domain"))
    return DiffDataProductItem(
        id=item.id,
        resource_type="dataProduct",
        outcome="blocked",
        reasons=sort_reasons(reasons),
    )


def _enforce_data_product_domain_dependencies(
    items: list[DiffDataProductItem],
    *,
    desired_products: tuple[DataProductDesiredState, ...],
    remote: RemoteStateV3,
    change_set,
    desired_domain_ids: set[str],
) -> list[DiffDataProductItem]:
    domain_by_product = {product.id: product.domain for product in desired_products}
    updated: list[DiffDataProductItem] = []
    for item in items:
        if item.outcome not in {"create", "replace"}:
            updated.append(item)
            continue
        domain_id = domain_by_product.get(item.id)
        if domain_id is None:
            updated.append(item)
            continue
        resolution = _resolve_domain(
            domain_id,
            remote=remote,
            change_set=change_set,
            desired_domain_ids=desired_domain_ids,
        )
        if resolution.status == "satisfied" or resolution.status == "depends_on_create":
            updated.append(item)
        else:
            updated.append(
                _block_data_product_for_domain(
                    item,
                    reason_code=resolution.reason_code or "plan.domain_unresolved",
                )
            )
    return updated


def _remote_data_product_capture_incomplete(
    config: GovernanceConfigV3, remote: RemoteStateV3
) -> bool:
    from purview_governance.config.models_v3 import DataProductResourceConfig

    has_dp_config = any(isinstance(r, DataProductResourceConfig) for r in config.resources)
    return has_dp_config and not remote.includes_data_product_capture


def _remote_glossary_term_capture_incomplete(
    config: GovernanceConfigV3, remote: RemoteStateV3
) -> bool:
    from purview_governance.config.models_v3 import GlossaryTermResourceConfig

    has_gt_config = any(isinstance(r, GlossaryTermResourceConfig) for r in config.resources)
    return has_gt_config and not remote.includes_glossary_term_capture


def _remote_capture_incomplete(config: GovernanceConfigV3, remote: RemoteStateV3) -> bool:
    return _remote_data_product_capture_incomplete(
        config, remote
    ) or _remote_glossary_term_capture_incomplete(config, remote)


def _mark_remote_capture_incomplete(items: list[DiffDataProductItem]) -> list[DiffDataProductItem]:
    from purview_governance.diff.reasons import reason, sort_reasons

    updated: list[DiffDataProductItem] = []
    for item in items:
        if item.outcome in {"create", "replace"}:
            reasons = list(item.reasons)
            reasons.append(reason("plan.remote_capture_incomplete", "/"))
            updated.append(
                DiffDataProductItem(
                    id=item.id,
                    resource_type="dataProduct",
                    outcome="blocked",
                    reasons=sort_reasons(reasons),
                )
            )
        else:
            updated.append(item)
    return updated


def _mark_glossary_remote_capture_incomplete(
    items: list[DiffGlossaryTermItem],
) -> list[DiffGlossaryTermItem]:
    from purview_governance.diff.reasons import reason, sort_reasons

    updated: list[DiffGlossaryTermItem] = []
    for item in items:
        if item.outcome in {"create", "replace"}:
            reasons = list(item.reasons)
            reasons.append(reason("plan.remote_capture_incomplete", "/"))
            updated.append(
                DiffGlossaryTermItem(
                    id=item.id,
                    resource_type="glossaryTerm",
                    outcome="blocked",
                    reasons=sort_reasons(reasons),
                )
            )
        else:
            updated.append(item)
    return updated


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

    if _remote_data_product_capture_incomplete(config, remote):
        dp_items = _mark_remote_capture_incomplete(_data_product_items(change_set))
        bd_items = _business_domain_items(change_set)
        gt_items = _glossary_term_items(change_set)
        change_set = DiffDocument(items=tuple([*bd_items, *dp_items, *gt_items]))

    if _remote_glossary_term_capture_incomplete(config, remote):
        gt_items = _mark_glossary_remote_capture_incomplete(_glossary_term_items(change_set))
        bd_items = _business_domain_items(change_set)
        dp_items = _data_product_items(change_set)
        change_set = DiffDocument(items=tuple([*bd_items, *dp_items, *gt_items]))

    desired_domain_ids = _desired_domain_ids(config)
    dp_items = _enforce_data_product_domain_dependencies(
        _data_product_items(change_set),
        desired_products=desired.data_products,
        remote=remote,
        change_set=change_set,
        desired_domain_ids=desired_domain_ids,
    )
    gt_items = enforce_glossary_term_dependencies(
        _glossary_term_items(change_set),
        desired_terms=desired.glossary_terms,
        remote=remote,
        change_set=change_set,
        desired_domain_ids=desired_domain_ids,
        resolve_domain=_resolve_domain,
    )
    bd_items = _business_domain_items(change_set)
    change_set = DiffDocument(
        items=tuple(sorted([*bd_items, *dp_items, *gt_items], key=_change_set_sort_key))
    )

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
    bd_change_items = _business_domain_items(change_set)
    dp_change_items = _data_product_items(change_set)
    gt_change_items = _glossary_term_items(change_set)

    parent_by_desired = {domain.id: domain.parent_id for domain in desired.business_domains}
    desired_ids = set(parent_by_desired.keys())

    create_ids = [item.id for item in bd_change_items if item.outcome == "create"]
    replace_ids = sorted(item.id for item in bd_change_items if item.outcome == "replace")

    eligible_creates = len(create_ids)
    observed = remote_observed_count_v3(remote)
    if observed + eligible_creates > MAX_BUSINESS_DOMAINS:
        raise PlanBuildError(
            "plan.business_domain_count_exceeded",
            f"resultant Business Domain count would exceed {MAX_BUSINESS_DOMAINS}",
        )

    parent_map = _build_resultant_parent_map(parent_by_desired, remote)
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
        item = next(item for item in bd_change_items if item.id == domain_id)
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

    dp_create_ids = sorted(item.id for item in dp_change_items if item.outcome == "create")
    dp_replace_ids = sorted(item.id for item in dp_change_items if item.outcome == "replace")
    for product_id in dp_create_ids:
        operations_list.append(
            PlanOperationV3(
                sequence=sequence,
                resource_type="dataProduct",
                id=product_id,
                action="create",
            )
        )
        sequence += 1
    for product_id in dp_replace_ids:
        item = next(item for item in dp_change_items if item.id == product_id)
        if any(reason.code == "remote.unsupported_configurable_field" for reason in item.reasons):
            continue
        if any(reason.code == "remote.status_blocks_replace" for reason in item.reasons):
            continue
        if any(reason.code == "plan.domain_move_unverified" for reason in item.reasons):
            continue
        operations_list.append(
            PlanOperationV3(
                sequence=sequence,
                resource_type="dataProduct",
                id=product_id,
                action="replace",
            )
        )
        sequence += 1

    parent_by_desired_gt = {term.id: term.parent_id for term in desired.glossary_terms}
    desired_gt_ids = set(parent_by_desired_gt.keys())
    gt_create_ids = [item.id for item in gt_change_items if item.outcome == "create"]
    gt_replace_ids = sorted(item.id for item in gt_change_items if item.outcome == "replace")
    ordered_gt_creates = _topological_create_order(
        desired_gt_ids, parent_by_desired_gt, gt_create_ids
    )
    for term_id in ordered_gt_creates:
        operations_list.append(
            PlanOperationV3(
                sequence=sequence,
                resource_type="glossaryTerm",
                id=term_id,
                action="create",
            )
        )
        sequence += 1
    for term_id in gt_replace_ids:
        item = next(item for item in gt_change_items if item.id == term_id)
        if any(reason.code == "remote.unsupported_configurable_field" for reason in item.reasons):
            continue
        if any(reason.code == "remote.status_blocks_replace" for reason in item.reasons):
            continue
        if any(
            reason.code == "plan.glossary_term_domain_move_unverified" for reason in item.reasons
        ):
            continue
        operations_list.append(
            PlanOperationV3(
                sequence=sequence,
                resource_type="glossaryTerm",
                id=term_id,
                action="replace",
            )
        )
        sequence += 1

    eligibility = "blocked" if counts["blocked"] > 0 else "ready"
    summary = PlanSummary(
        total=len(change_set.items),
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
