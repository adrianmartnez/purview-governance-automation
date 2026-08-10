"""Frozen models for purview-execution-result/v1."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal

from purview_governance.apply.identity import RESULT_API_VERSION, compute_result_identity
from purview_governance.remote_state.canonical import dumps_canonical

ExecutionStatus = Literal[
    "dry-run-ready",
    "applied",
    "blocked",
    "wrong-target",
    "stale",
    "failed-before-write",
    "write-failed",
    "indeterminate",
]
OperationResultStatus = Literal["not-run", "succeeded", "failed", "unknown"]
PlanAction = Literal["create", "replace"]


class ExecutionMode(Enum):
    """Explicit dry-run vs authorized mutation."""

    DRY_RUN = "dry-run"
    APPLY = "apply"


FAILURE_CODES_BY_STATUS: dict[str, frozenset[str] | None] = {
    "dry-run-ready": None,
    "applied": None,
    "blocked": frozenset({"apply.plan_blocked"}),
    "wrong-target": frozenset({"apply.wrong_target"}),
    "stale": frozenset({"apply.stale_plan"}),
    "failed-before-write": frozenset(
        {
            "apply.payload_preflight_failed",
            "apply.authentication_failed",
            "apply.remote_read_failed",
            "apply.remote_state_failed",
        }
    ),
    "write-failed": frozenset({"apply.write_rejected", "apply.write_auth_failed"}),
    "indeterminate": frozenset({"apply.write_outcome_unknown"}),
}


@dataclass(frozen=True, slots=True)
class OperationResult:
    sequence: int
    resource_type: Literal["dataSource"]
    name: str
    action: PlanAction
    status: OperationResultStatus

    def to_document(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "name": self.name,
            "sequence": self.sequence,
            "status": self.status,
            "type": self.resource_type,
        }


@dataclass(frozen=True, slots=True)
class ExecutionFailure:
    code: str

    def to_document(self) -> dict[str, str]:
        return {"code": self.code}


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Versioned purview-execution-result/v1 artifact model."""

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
    operations: tuple[OperationResult, ...]
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
        from purview_governance.apply.validation import (
            validate_result_document_for_serialization,
        )

        document = self.to_document()
        validate_result_document_for_serialization(document)
        return dumps_canonical(document)


def build_execution_result_from_parts(
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
    operations: tuple[OperationResult, ...],
    failure: ExecutionFailure | None,
) -> ExecutionResult:
    """Assemble a result and compute ``resultIdentity`` (caller should self-validate)."""
    provisional = ExecutionResult(
        api_version=RESULT_API_VERSION,
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
    return ExecutionResult(
        api_version=RESULT_API_VERSION,
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


def operations_from_document(document: list[dict[str, Any]]) -> tuple[OperationResult, ...]:
    return tuple(
        OperationResult(
            sequence=raw["sequence"],
            resource_type="dataSource",
            name=raw["name"],
            action=raw["action"],
            status=raw["status"],
        )
        for raw in document
    )
