"""Frozen models for purview-execution-result/v2."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from purview_governance.apply.identity import RESULT_API_VERSION_V2, compute_result_identity
from purview_governance.apply.models import (
    FAILURE_CODES_BY_STATUS,
    ExecutionFailure,
    ExecutionMode,
    ExecutionStatus,
    OperationResultStatus,
    PlanAction,
)
from purview_governance.remote_state.canonical import dumps_canonical

ResourceTypeV2 = Literal["dataSource", "classificationRule", "scanRuleSet", "scan"]

__all__ = [
    "FAILURE_CODES_BY_STATUS",
    "ExecutionFailure",
    "ExecutionMode",
    "ExecutionResultV2",
    "ExecutionStatus",
    "OperationResultV2",
    "ResourceTypeV2",
    "build_execution_result_v2_from_parts",
    "operations_v2_from_document",
]


@dataclass(frozen=True, slots=True)
class OperationResultV2:
    sequence: int
    resource_type: ResourceTypeV2
    name: str
    action: PlanAction
    status: OperationResultStatus
    data_source_name: str | None = None

    def to_document(self) -> dict[str, Any]:
        doc: dict[str, Any] = {
            "action": self.action,
            "name": self.name,
            "sequence": self.sequence,
            "status": self.status,
            "type": self.resource_type,
        }
        if self.resource_type == "scan":
            doc["dataSourceName"] = self.data_source_name
        return doc


@dataclass(frozen=True, slots=True)
class ExecutionResultV2:
    """Versioned purview-execution-result/v2 artifact model."""

    api_version: str
    plan_identity: str
    planned_target_context_identity: str
    execution_target_context_identity: str | None
    planned_remote_state_identity: str
    observed_remote_state_identity: str | None
    mode: ExecutionMode
    status: ExecutionStatus
    writes_performed: int
    writes_attempted: int
    writes_unknown: int
    operations: tuple[OperationResultV2, ...]
    failure: ExecutionFailure | None
    result_identity: str

    def to_document(self) -> dict[str, Any]:
        return {
            "apiVersion": self.api_version,
            "executionTargetContextIdentity": self.execution_target_context_identity,
            "failure": None if self.failure is None else self.failure.to_document(),
            "mode": self.mode.value,
            "observedRemoteStateIdentity": self.observed_remote_state_identity,
            "operations": [item.to_document() for item in self.operations],
            "planIdentity": self.plan_identity,
            "plannedRemoteStateIdentity": self.planned_remote_state_identity,
            "plannedTargetContextIdentity": self.planned_target_context_identity,
            "resultIdentity": self.result_identity,
            "status": self.status,
            "writesAttempted": self.writes_attempted,
            "writesPerformed": self.writes_performed,
            "writesUnknown": self.writes_unknown,
        }

    def document_without_result_identity(self) -> dict[str, Any]:
        doc = self.to_document()
        del doc["resultIdentity"]
        return doc

    def to_canonical_json(self) -> str:
        """Serialize through shared schema+semantic integrity (official persistence boundary)."""
        from purview_governance.apply.validation_v2 import (
            validate_result_document_v2_for_serialization,
        )

        document = self.to_document()
        validate_result_document_v2_for_serialization(document)
        return dumps_canonical(document)


def build_execution_result_v2_from_parts(
    *,
    plan_identity: str,
    planned_target_context_identity: str,
    execution_target_context_identity: str | None,
    planned_remote_state_identity: str,
    observed_remote_state_identity: str | None,
    mode: ExecutionMode,
    status: ExecutionStatus,
    writes_performed: int,
    writes_attempted: int,
    writes_unknown: int,
    operations: tuple[OperationResultV2, ...],
    failure: ExecutionFailure | None,
) -> ExecutionResultV2:
    """Assemble a v2 result and compute ``resultIdentity``."""
    provisional = ExecutionResultV2(
        api_version=RESULT_API_VERSION_V2,
        plan_identity=plan_identity,
        planned_target_context_identity=planned_target_context_identity,
        execution_target_context_identity=execution_target_context_identity,
        planned_remote_state_identity=planned_remote_state_identity,
        observed_remote_state_identity=observed_remote_state_identity,
        mode=mode,
        status=status,
        writes_performed=writes_performed,
        writes_attempted=writes_attempted,
        writes_unknown=writes_unknown,
        operations=operations,
        failure=failure,
        result_identity="",
    )
    result_identity = compute_result_identity(provisional.document_without_result_identity())
    return ExecutionResultV2(
        api_version=RESULT_API_VERSION_V2,
        plan_identity=plan_identity,
        planned_target_context_identity=planned_target_context_identity,
        execution_target_context_identity=execution_target_context_identity,
        planned_remote_state_identity=planned_remote_state_identity,
        observed_remote_state_identity=observed_remote_state_identity,
        mode=mode,
        status=status,
        writes_performed=writes_performed,
        writes_attempted=writes_attempted,
        writes_unknown=writes_unknown,
        operations=operations,
        failure=failure,
        result_identity=result_identity,
    )


def operations_v2_from_document(document: list[dict[str, Any]]) -> tuple[OperationResultV2, ...]:
    return tuple(
        OperationResultV2(
            sequence=raw["sequence"],
            resource_type=raw["type"],
            name=raw["name"],
            action=raw["action"],
            status=raw["status"],
            data_source_name=raw.get("dataSourceName"),
        )
        for raw in document
    )
