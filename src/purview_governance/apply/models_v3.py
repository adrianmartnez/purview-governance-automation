"""Frozen models for purview-execution-result/v3."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from purview_governance.apply.identity import RESULT_API_VERSION_V3, compute_result_identity
from purview_governance.apply.models import (
    ExecutionFailure,
    ExecutionMode,
    OperationResultStatus,
    PlanAction,
)
from purview_governance.remote_state.canonical import dumps_canonical

ResourceTypeV3 = Literal["businessDomain", "dataProduct", "glossaryTerm"]

ExecutionStatusV3 = Literal[
    "dry-run-ready",
    "applied",
    "blocked",
    "wrong-target",
    "stale",
    "failed-before-write",
    "write-failed",
    "indeterminate",
    "partial",
]

FAILURE_CODES_BY_STATUS_V3: dict[str, frozenset[str] | None] = {
    "dry-run-ready": None,
    "applied": None,
    "blocked": frozenset({"apply.plan_blocked"}),
    "wrong-target": frozenset({"apply.wrong_target"}),
    "stale": frozenset({"apply.stale_plan"}),
    "failed-before-write": frozenset(
        {
            "apply.payload_preflight_failed",
            "apply.payload_semantics_unverified",
            "apply.authentication_failed",
            "apply.remote_read_failed",
            "apply.remote_state_failed",
            "apply.remote_state_identity_mismatch",
            "apply.invalid_remote_state",
            "apply.tenant_binding_unsupported",
        }
    ),
    "partial": frozenset(
        {
            "apply.pre_write_stale_after_writes",
            "apply.pre_write_auth_failed_after_writes",
            "apply.pre_write_read_failed_after_writes",
        }
    ),
    "write-failed": frozenset({"apply.write_rejected", "apply.write_auth_failed"}),
    "indeterminate": frozenset({"apply.write_outcome_unknown", "apply.write_response_invalid"}),
}

__all__ = [
    "FAILURE_CODES_BY_STATUS_V3",
    "ExecutionFailure",
    "ExecutionMode",
    "ExecutionResultV3",
    "ExecutionStatusV3",
    "OperationResultV3",
    "ResourceTypeV3",
    "build_execution_result_v3_from_parts",
    "operations_v3_from_document",
]


@dataclass(frozen=True, slots=True)
class OperationResultV3:
    sequence: int
    resource_type: ResourceTypeV3
    resource_id: str
    action: PlanAction
    status: OperationResultStatus

    def to_document(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "id": self.resource_id,
            "sequence": self.sequence,
            "status": self.status,
            "type": self.resource_type,
        }


@dataclass(frozen=True, slots=True)
class ExecutionResultV3:
    """Versioned purview-execution-result/v3 artifact model."""

    api_version: str
    plan_identity: str
    planned_target_context_identity: str
    execution_target_context_identity: str | None
    planned_remote_state_identity: str
    observed_remote_state_identity: str | None
    mode: ExecutionMode
    status: ExecutionStatusV3
    writes_performed: int
    writes_attempted: int
    writes_unknown: int
    operations: tuple[OperationResultV3, ...]
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
        from purview_governance.apply.validation_v3 import (
            validate_result_document_v3_for_serialization,
        )

        document = self.to_document()
        validate_result_document_v3_for_serialization(document)
        return dumps_canonical(document)


def build_execution_result_v3_from_parts(
    *,
    plan_identity: str,
    planned_target_context_identity: str,
    execution_target_context_identity: str | None,
    planned_remote_state_identity: str,
    observed_remote_state_identity: str | None,
    mode: ExecutionMode,
    status: ExecutionStatusV3,
    writes_performed: int,
    writes_attempted: int,
    writes_unknown: int,
    operations: tuple[OperationResultV3, ...],
    failure: ExecutionFailure | None,
) -> ExecutionResultV3:
    provisional = ExecutionResultV3(
        api_version=RESULT_API_VERSION_V3,
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
    return ExecutionResultV3(
        api_version=RESULT_API_VERSION_V3,
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


def operations_v3_from_document(document: list[dict[str, Any]]) -> tuple[OperationResultV3, ...]:
    return tuple(
        OperationResultV3(
            sequence=raw["sequence"],
            resource_type=raw["type"],
            resource_id=raw["id"],
            action=raw["action"],
            status=raw["status"],
        )
        for raw in document
    )
