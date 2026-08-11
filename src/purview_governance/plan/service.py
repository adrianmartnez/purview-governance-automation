"""Offline governance plan builder (v1 and v2; builders perform no writes)."""

from __future__ import annotations

from purview_governance.config.models import (
    CONFIG_API_VERSION_V2,
    DataSourceResourceConfig,
    GovernanceConfig,
    ScanResourceConfig,
    ScanRuleSetResourceConfig,
)
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
    build_plan_from_parts_v2,
)
from purview_governance.plan.validation import (
    validate_governance_config_for_planning,
    validate_governance_config_for_planning_v2,
    validate_plan_document_for_serialization,
    validate_remote_state_for_planning,
    validate_remote_state_v2_for_planning,
)
from purview_governance.remote_state.models import RemoteState, RemoteStateV2

_TYPE_RANK: dict[str, int] = {
    "dataSource": 0,
    "classificationRule": 1,
    "scanRuleSet": 2,
    "scan": 3,
}


def _config_has_multi_resource(config: GovernanceConfig) -> bool:
    return any(
        isinstance(resource, (ScanResourceConfig, ScanRuleSetResourceConfig))
        for resource in config.resources
    )


def _summarize_change_set(change_set) -> tuple[dict[str, int], list[tuple[str, str, str | None]]]:
    counts = {
        "create": 0,
        "replace": 0,
        "no-op": 0,
        "remote-only": 0,
        "blocked": 0,
    }
    create_replace: list[tuple[str, str, str | None]] = []
    for item in change_set.items:
        counts[item.outcome] += 1
        if item.outcome in {"create", "replace"}:
            create_replace.append((item.outcome, item.name, item.data_source_name))
    return counts, create_replace


def build_governance_plan(
    config: GovernanceConfig,
    remote_state: RemoteState,
) -> GovernancePlan:
    """Build a deterministic purview-governance-plan/v1 from config + remote state.

    Pure/offline: derives desired and diff internally. Performs zero remote writes.
    A plan with ``executionEligibility=blocked`` must produce zero writes in apply (#15).

    Configurations that declare Scan or Scan Rule Set resources (or config/v2) must use
    ``build_governance_plan_v2``.
    """
    if config.api_version == CONFIG_API_VERSION_V2 or _config_has_multi_resource(config):
        raise PlanBuildError(
            "plan.requires_v2_builder",
            "scan/scanRuleSet or config/v2 requires build_governance_plan_v2",
        )

    normalized_endpoint = validate_governance_config_for_planning(config)
    validate_remote_state_for_planning(remote_state)

    # v1 plans only compare Data Sources even if mapping could widen later.
    ds_only = GovernanceConfig(
        api_version=config.api_version,
        target=config.target,
        authentication=config.authentication,
        resources=tuple(
            resource
            for resource in config.resources
            if isinstance(resource, DataSourceResourceConfig)
        ),
    )
    desired = desired_state_from_config(ds_only)
    for resource in ds_only.resources:
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
        configuration_api_version=config.api_version,
    )

    counts, create_replace = _summarize_change_set(change_set)
    create_replace.sort(key=lambda pair: (_TYPE_RANK["dataSource"], pair[2] or "", pair[1]))
    operations = tuple(
        PlanOperation(
            sequence=index,
            resource_type="dataSource",
            name=name,
            action=action,  # type: ignore[arg-type]
        )
        for index, (action, name, _parent) in enumerate(create_replace, start=1)
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


def build_governance_plan_v2(
    config: GovernanceConfig,
    remote_state: RemoteStateV2,
) -> GovernancePlan:
    """Build a purview-governance-plan/v2 (DS + CR + scans + Custom SRS).

    Pure/offline: no network writes and no live-tenant claim. The resulting plan
    artifact can later be consumed by controlled apply (plan/v2 path).
    """
    normalized_endpoint = validate_governance_config_for_planning_v2(config)
    validate_remote_state_v2_for_planning(remote_state)

    desired = desired_state_from_config(config)
    change_set = diff_desired_vs_remote(desired, remote_state)

    target_identity = compute_target_context_identity(normalized_endpoint)
    desired_doc = desired.to_document(multi_resource=True)
    desired_identity = compute_desired_state_identity(desired_doc)
    material_identity = compute_material_configuration_identity(
        target_context_identity=target_identity,
        desired_state_identity=desired_identity,
        configuration_api_version=config.api_version,
    )

    counts, create_replace = _summarize_change_set(change_set)
    # Rebuild with resource types from change set for correct operation typing.
    typed_ops: list[tuple[str, str, str, str | None]] = []
    for item in change_set.items:
        if item.outcome in {"create", "replace"}:
            typed_ops.append((item.outcome, item.resource_type, item.name, item.data_source_name))
    typed_ops.sort(key=lambda row: (_TYPE_RANK[row[1]], row[3] or "", row[2]))
    operations = tuple(
        PlanOperation(
            sequence=index,
            resource_type=resource_type,  # type: ignore[arg-type]
            name=name,
            action=action,  # type: ignore[arg-type]
            data_source_name=parent,
        )
        for index, (action, resource_type, name, parent) in enumerate(typed_ops, start=1)
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

    plan = build_plan_from_parts_v2(
        configuration_api_version=config.api_version,
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
