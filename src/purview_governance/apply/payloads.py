"""Derive Create Or Replace PUT payloads solely from plan desired-state snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from purview_governance.apply.errors import ApplyValidationError
from purview_governance.desired.models import (
    ClassificationRuleDesiredState,
    DataSourceDesiredState,
    ScanDesiredState,
    ScanRuleSetDesiredState,
)
from purview_governance.plan.models import GovernancePlan, PlanOperation
from purview_governance.scanning.names import (
    validate_classification_rule_name,
    validate_data_source_name,
    validate_scan_name,
    validate_scan_ruleset_name,
)

ResourceType = Literal["dataSource", "classificationRule", "scanRuleSet", "scan"]


@dataclass(frozen=True, slots=True)
class MutationIntent:
    """v1 Data Source mutation intent (frozen resource_type)."""

    sequence: int
    resource_type: Literal["dataSource"]
    name: str
    action: Literal["create", "replace"]
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class MutationIntentV2:
    """Multi-resource mutation intent with composite Scan identity."""

    sequence: int
    resource_type: ResourceType
    name: str
    action: Literal["create", "replace"]
    payload: dict[str, Any]
    data_source_name: str | None = None


def azure_storage_put_payload(desired: DataSourceDesiredState) -> dict[str, Any]:
    """Exact minimal AzureStorage Create Or Replace request body for v1/v2."""
    return {
        "kind": "AzureStorage",
        "properties": {
            "collection": {"referenceName": desired.collection_reference_name},
            "endpoint": desired.endpoint,
        },
    }


def custom_classification_rule_put_payload(
    desired: ClassificationRuleDesiredState,
) -> dict[str, Any]:
    """Exact Custom Classification Rule Create Or Replace body from desired."""
    properties: dict[str, Any] = {
        "classificationName": desired.classification_name,
        "columnPatterns": [item.to_document() for item in desired.column_patterns],
        "dataPatterns": [item.to_document() for item in desired.data_patterns],
        "minimumPercentageMatch": desired.minimum_percentage_match,
        "ruleStatus": desired.rule_status,
    }
    if desired.description is not None:
        properties["description"] = desired.description
    return {"kind": "Custom", "properties": properties}


def custom_azure_storage_scan_ruleset_put_payload(
    desired: ScanRuleSetDesiredState,
) -> dict[str, Any]:
    """Exact Custom AzureStorage Scan Rule Set Create Or Replace body from desired."""
    properties: dict[str, Any] = {
        "scanningRule": {"fileExtensions": list(desired.file_extensions)},
        "excludedSystemClassifications": list(desired.excluded_system_classifications),
        "includedCustomClassificationRuleNames": list(
            desired.included_custom_classification_rule_names
        ),
    }
    if desired.description is not None:
        properties["description"] = desired.description
    return {
        "kind": "AzureStorage",
        "scanRulesetType": "Custom",
        "properties": properties,
    }


def azure_storage_msi_scan_put_payload(desired: ScanDesiredState) -> dict[str, Any]:
    """Exact AzureStorageMsi Scan Create Or Replace body (includes top-level parent)."""
    return {
        "dataSourceName": desired.data_source_name,
        "kind": "AzureStorageMsi",
        "properties": {
            "collection": {"referenceName": desired.collection_reference_name},
            "scanRulesetName": desired.scan_ruleset_name,
            "scanRulesetType": desired.scan_ruleset_type,
        },
    }


def materialize_mutation_intents(plan: GovernancePlan) -> tuple[MutationIntent, ...]:
    """Build frozen mutation intents for every planned create/replace operation (v1)."""
    by_name = {item.name: item for item in plan.desired_state.data_sources}
    intents: list[MutationIntent] = []
    for operation in plan.operations:
        _validate_operation_v1(operation)
        desired = by_name.get(operation.name)
        if desired is None:
            raise ApplyValidationError(
                "apply.payload_preflight_failed",
                "planned operation has no matching desired resource",
            )
        name_failed = False
        try:
            validated_name = validate_data_source_name(operation.name)
        except Exception:
            name_failed = True
        if name_failed:
            raise ApplyValidationError(
                "apply.payload_preflight_failed",
                "planned operation name is invalid",
            )
        if desired.kind != "AzureStorage":
            raise ApplyValidationError(
                "apply.payload_preflight_failed",
                "only AzureStorage mutations are supported",
            )
        intents.append(
            MutationIntent(
                sequence=operation.sequence,
                resource_type="dataSource",
                name=validated_name,
                action=operation.action,
                payload=azure_storage_put_payload(desired),
            )
        )
    return tuple(intents)


def materialize_mutation_intents_v2(plan: GovernancePlan) -> tuple[MutationIntentV2, ...]:
    """Build type-aware mutation intents for plan/v2 (composite Scan identity)."""
    ds_index = _index_by_name(plan.desired_state.data_sources, label="dataSource")
    cr_index = _index_by_name(plan.desired_state.classification_rules, label="classificationRule")
    srs_index = _index_by_name(plan.desired_state.scan_rule_sets, label="scanRuleSet")
    scan_index = _index_scans(plan.desired_state.scans)

    _validate_same_plan_prerequisites(plan)

    intents: list[MutationIntentV2] = []
    for operation in plan.operations:
        if operation.action not in {"create", "replace"}:
            raise ApplyValidationError(
                "apply.payload_preflight_failed",
                "only create/replace operations are supported",
            )
        if operation.resource_type == "dataSource":
            intents.append(_materialize_data_source(operation, ds_index))
        elif operation.resource_type == "classificationRule":
            intents.append(_materialize_classification_rule(operation, cr_index))
        elif operation.resource_type == "scanRuleSet":
            intents.append(_materialize_scan_rule_set(operation, srs_index))
        elif operation.resource_type == "scan":
            intents.append(_materialize_scan(operation, scan_index))
        else:
            raise ApplyValidationError(
                "apply.payload_preflight_failed",
                "plan contains unsupported mutation operations",
            )
    return tuple(intents)


def _validate_operation_v1(operation: PlanOperation) -> None:
    if operation.resource_type != "dataSource":
        raise ApplyValidationError(
            "apply.payload_preflight_failed",
            "only dataSource operations are supported",
        )
    if operation.action not in {"create", "replace"}:
        raise ApplyValidationError(
            "apply.payload_preflight_failed",
            "only create/replace operations are supported",
        )


def _index_by_name(items: tuple[Any, ...], *, label: str) -> dict[str, Any]:
    index: dict[str, Any] = {}
    for item in items:
        if item.name in index:
            raise ApplyValidationError(
                "apply.payload_preflight_failed",
                f"duplicate desired {label} name",
            )
        index[item.name] = item
    return index


def _index_scans(items: tuple[ScanDesiredState, ...]) -> dict[tuple[str, str], ScanDesiredState]:
    index: dict[tuple[str, str], ScanDesiredState] = {}
    for item in items:
        key = (item.data_source_name, item.name)
        if key in index:
            raise ApplyValidationError(
                "apply.payload_preflight_failed",
                "duplicate desired scan identity",
            )
        index[key] = item
    return index


def _materialize_data_source(
    operation: PlanOperation,
    index: dict[str, DataSourceDesiredState],
) -> MutationIntentV2:
    desired = index.get(operation.name)
    if desired is None:
        raise ApplyValidationError(
            "apply.payload_preflight_failed",
            "planned operation has no matching desired resource",
        )
    try:
        validated_name = validate_data_source_name(operation.name)
    except Exception as exc:
        raise ApplyValidationError(
            "apply.payload_preflight_failed",
            "planned operation name is invalid",
        ) from exc
    if desired.kind != "AzureStorage":
        raise ApplyValidationError(
            "apply.payload_preflight_failed",
            "only AzureStorage dataSource mutations are supported",
        )
    return MutationIntentV2(
        sequence=operation.sequence,
        resource_type="dataSource",
        name=validated_name,
        action=operation.action,  # type: ignore[arg-type]
        payload=azure_storage_put_payload(desired),
    )


def _materialize_classification_rule(
    operation: PlanOperation,
    index: dict[str, ClassificationRuleDesiredState],
) -> MutationIntentV2:
    desired = index.get(operation.name)
    if desired is None:
        raise ApplyValidationError(
            "apply.payload_preflight_failed",
            "planned operation has no matching desired resource",
        )
    try:
        validated_name = validate_classification_rule_name(operation.name)
    except Exception as exc:
        raise ApplyValidationError(
            "apply.payload_preflight_failed",
            "planned operation name is invalid",
        ) from exc
    if desired.kind != "Custom":
        raise ApplyValidationError(
            "apply.payload_preflight_failed",
            "only Custom classificationRule mutations are supported",
        )
    return MutationIntentV2(
        sequence=operation.sequence,
        resource_type="classificationRule",
        name=validated_name,
        action=operation.action,  # type: ignore[arg-type]
        payload=custom_classification_rule_put_payload(desired),
    )


def _materialize_scan_rule_set(
    operation: PlanOperation,
    index: dict[str, ScanRuleSetDesiredState],
) -> MutationIntentV2:
    desired = index.get(operation.name)
    if desired is None:
        raise ApplyValidationError(
            "apply.payload_preflight_failed",
            "planned operation has no matching desired resource",
        )
    try:
        validated_name = validate_scan_ruleset_name(operation.name)
    except Exception as exc:
        raise ApplyValidationError(
            "apply.payload_preflight_failed",
            "planned operation name is invalid",
        ) from exc
    if desired.kind != "AzureStorage" or desired.scan_ruleset_type != "Custom":
        raise ApplyValidationError(
            "apply.payload_preflight_failed",
            "only Custom AzureStorage scanRuleSet mutations are supported",
        )
    return MutationIntentV2(
        sequence=operation.sequence,
        resource_type="scanRuleSet",
        name=validated_name,
        action=operation.action,  # type: ignore[arg-type]
        payload=custom_azure_storage_scan_ruleset_put_payload(desired),
    )


def _materialize_scan(
    operation: PlanOperation,
    index: dict[tuple[str, str], ScanDesiredState],
) -> MutationIntentV2:
    if not operation.data_source_name:
        raise ApplyValidationError(
            "apply.payload_preflight_failed",
            "scan operation requires dataSourceName",
        )
    try:
        parent = validate_data_source_name(operation.data_source_name)
        validated_name = validate_scan_name(operation.name)
    except Exception as exc:
        raise ApplyValidationError(
            "apply.payload_preflight_failed",
            "planned scan identity is invalid",
        ) from exc

    desired = index.get((parent, validated_name))
    if desired is None:
        raise ApplyValidationError(
            "apply.payload_preflight_failed",
            "planned operation has no matching desired resource",
        )
    if desired.data_source_name != parent:
        raise ApplyValidationError(
            "apply.payload_preflight_failed",
            "scan parent identity mismatch between operation and desired",
        )
    if desired.kind != "AzureStorageMsi":
        raise ApplyValidationError(
            "apply.payload_preflight_failed",
            "only AzureStorageMsi scan mutations are supported",
        )

    payload = azure_storage_msi_scan_put_payload(desired)
    body_parent = payload.get("dataSourceName")
    if body_parent != parent:
        raise ApplyValidationError(
            "apply.payload_preflight_failed",
            "scan parent identity mismatch in wire payload",
        )

    return MutationIntentV2(
        sequence=operation.sequence,
        resource_type="scan",
        name=validated_name,
        action=operation.action,  # type: ignore[arg-type]
        payload=payload,
        data_source_name=parent,
    )


def _validate_same_plan_prerequisites(plan: GovernancePlan) -> None:
    """Fail-closed when same-plan prerequisites appear after their consumers."""
    ds_ops = {op.name: op.sequence for op in plan.operations if op.resource_type == "dataSource"}
    cr_ops = {
        op.name: op.sequence for op in plan.operations if op.resource_type == "classificationRule"
    }
    srs_ops = {op.name: op.sequence for op in plan.operations if op.resource_type == "scanRuleSet"}

    desired_srs = {item.name: item for item in plan.desired_state.scan_rule_sets}
    desired_scans = {(item.data_source_name, item.name): item for item in plan.desired_state.scans}

    for op in plan.operations:
        if op.resource_type == "scanRuleSet":
            desired = desired_srs.get(op.name)
            if desired is None:
                continue
            for rule_name in desired.included_custom_classification_rule_names:
                prereq = cr_ops.get(rule_name)
                if prereq is not None and prereq >= op.sequence:
                    raise ApplyValidationError(
                        "apply.payload_preflight_failed",
                        "classificationRule prerequisite must precede scanRuleSet",
                    )
        elif op.resource_type == "scan":
            if not op.data_source_name:
                continue
            desired = desired_scans.get((op.data_source_name, op.name))
            if desired is None:
                continue
            parent_seq = ds_ops.get(desired.data_source_name)
            if parent_seq is not None and parent_seq >= op.sequence:
                raise ApplyValidationError(
                    "apply.payload_preflight_failed",
                    "dataSource prerequisite must precede scan",
                )
            if desired.scan_ruleset_type == "Custom":
                srs_seq = srs_ops.get(desired.scan_ruleset_name)
                if srs_seq is not None and srs_seq >= op.sequence:
                    raise ApplyValidationError(
                        "apply.payload_preflight_failed",
                        "scanRuleSet prerequisite must precede scan",
                    )
