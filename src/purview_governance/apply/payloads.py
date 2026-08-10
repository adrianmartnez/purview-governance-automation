"""Derive AzureStorage PUT payloads solely from plan desired-state snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from purview_governance.apply.errors import ApplyValidationError
from purview_governance.desired.models import DataSourceDesiredState
from purview_governance.plan.models import GovernancePlan, PlanOperation
from purview_governance.scanning.names import validate_data_source_name


@dataclass(frozen=True, slots=True)
class MutationIntent:
    sequence: int
    resource_type: Literal["dataSource"]
    name: str
    action: Literal["create", "replace"]
    payload: dict[str, Any]


def azure_storage_put_payload(desired: DataSourceDesiredState) -> dict[str, Any]:
    """Exact minimal AzureStorage Create Or Replace request body for v1."""
    return {
        "kind": "AzureStorage",
        "properties": {
            "collection": {"referenceName": desired.collection_reference_name},
            "endpoint": desired.endpoint,
        },
    }


def materialize_mutation_intents(plan: GovernancePlan) -> tuple[MutationIntent, ...]:
    """Build frozen mutation intents for every planned create/replace operation."""
    by_name = {item.name: item for item in plan.desired_state.data_sources}
    intents: list[MutationIntent] = []
    for operation in plan.operations:
        _validate_operation(operation)
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


def _validate_operation(operation: PlanOperation) -> None:
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
