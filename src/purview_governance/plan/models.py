"""Frozen models for purview-governance-plan/v1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from purview_governance.desired.models import DataSourceDesiredState, DesiredState
from purview_governance.diff.models import DiffDocument, DiffItem, DiffOutcome, DiffReason
from purview_governance.plan.identity import (
    CONFIGURATION_API_VERSION,
    PLAN_API_VERSION,
    compute_plan_identity,
)
from purview_governance.remote_state.canonical import dumps_canonical

ExecutionEligibility = Literal["ready", "blocked"]
PlanAction = Literal["create", "replace"]


@dataclass(frozen=True, slots=True)
class PlanTargetContext:
    endpoint: str
    identity: str

    def to_document(self) -> dict[str, str]:
        return {"endpoint": self.endpoint, "identity": self.identity}


@dataclass(frozen=True, slots=True)
class PlanIdentities:
    material_configuration: str
    desired_state: str
    remote_state: str

    def to_document(self) -> dict[str, str]:
        return {
            "desiredState": self.desired_state,
            "materialConfiguration": self.material_configuration,
            "remoteState": self.remote_state,
        }


@dataclass(frozen=True, slots=True)
class PlanOperation:
    sequence: int
    resource_type: Literal["dataSource"]
    name: str
    action: PlanAction

    def to_document(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "name": self.name,
            "sequence": self.sequence,
            "type": self.resource_type,
        }


@dataclass(frozen=True, slots=True)
class PlanSummary:
    total: int
    create: int
    replace: int
    no_op: int
    remote_only: int
    blocked: int
    operations: int

    def to_document(self) -> dict[str, int]:
        return {
            "blocked": self.blocked,
            "create": self.create,
            "noOp": self.no_op,
            "operations": self.operations,
            "remoteOnly": self.remote_only,
            "replace": self.replace,
            "total": self.total,
        }


@dataclass(frozen=True, slots=True)
class GovernancePlan:
    """Versioned purview-governance-plan/v1 artifact model."""

    api_version: str
    configuration_api_version: str
    target_context: PlanTargetContext
    identities: PlanIdentities
    desired_state: DesiredState
    change_set: DiffDocument
    execution_eligibility: ExecutionEligibility
    operations: tuple[PlanOperation, ...]
    summary: PlanSummary
    plan_identity: str

    def to_document(self) -> dict[str, Any]:
        """Return the plain plan document (not the trusted persistence boundary)."""
        return {
            "apiVersion": self.api_version,
            "changeSet": self.change_set.to_document(),
            "configurationApiVersion": self.configuration_api_version,
            "desiredState": self.desired_state.to_document(),
            "executionEligibility": self.execution_eligibility,
            "identities": self.identities.to_document(),
            "operations": [item.to_document() for item in self.operations],
            "planIdentity": self.plan_identity,
            "summary": self.summary.to_document(),
            "targetContext": self.target_context.to_document(),
        }

    def document_without_plan_identity(self) -> dict[str, Any]:
        doc = self.to_document()
        del doc["planIdentity"]
        return doc

    def to_canonical_json(self) -> str:
        """Serialize through shared schema+semantic integrity (official persistence boundary)."""
        from purview_governance.plan.validation import validate_plan_document_for_serialization

        document = self.to_document()
        validate_plan_document_for_serialization(document)
        return dumps_canonical(document)


def build_plan_from_parts(
    *,
    target_context: PlanTargetContext,
    identities: PlanIdentities,
    desired_state: DesiredState,
    change_set: DiffDocument,
    execution_eligibility: ExecutionEligibility,
    operations: tuple[PlanOperation, ...],
    summary: PlanSummary,
) -> GovernancePlan:
    """Assemble a plan and compute ``planIdentity`` (caller must self-validate afterward)."""
    provisional = GovernancePlan(
        api_version=PLAN_API_VERSION,
        configuration_api_version=CONFIGURATION_API_VERSION,
        target_context=target_context,
        identities=identities,
        desired_state=desired_state,
        change_set=change_set,
        execution_eligibility=execution_eligibility,
        operations=operations,
        summary=summary,
        plan_identity="",
    )
    plan_identity = compute_plan_identity(provisional.document_without_plan_identity())
    return GovernancePlan(
        api_version=PLAN_API_VERSION,
        configuration_api_version=CONFIGURATION_API_VERSION,
        target_context=target_context,
        identities=identities,
        desired_state=desired_state,
        change_set=change_set,
        execution_eligibility=execution_eligibility,
        operations=operations,
        summary=summary,
        plan_identity=plan_identity,
    )


def desired_state_from_document(document: dict[str, Any]) -> DesiredState:
    items: list[DataSourceDesiredState] = []
    for raw in document.get("dataSources", []):
        props = raw["properties"]
        items.append(
            DataSourceDesiredState(
                name=raw["name"],
                kind="AzureStorage",
                endpoint=props["endpoint"],
                collection_reference_name=props["collection"]["referenceName"],
            )
        )
    return DesiredState(data_sources=tuple(items))


def change_set_from_document(document: dict[str, Any]) -> DiffDocument:
    items: list[DiffItem] = []
    for raw in document.get("items", []):
        reasons = tuple(
            DiffReason(
                code=reason["code"],
                path=reason["path"],
                before=reason.get("before"),
                after=reason.get("after"),
            )
            for reason in raw["reasons"]
        )
        outcome: DiffOutcome = raw["outcome"]
        items.append(
            DiffItem(
                name=raw["name"],
                resource_type="dataSource",
                outcome=outcome,
                reasons=reasons,
            )
        )
    return DiffDocument(items=tuple(items))


def operations_from_document(raw_operations: list[dict[str, Any]]) -> tuple[PlanOperation, ...]:
    return tuple(
        PlanOperation(
            sequence=int(item["sequence"]),
            resource_type="dataSource",
            name=item["name"],
            action=item["action"],
        )
        for item in raw_operations
    )


def summary_from_document(raw: dict[str, Any]) -> PlanSummary:
    return PlanSummary(
        total=int(raw["total"]),
        create=int(raw["create"]),
        replace=int(raw["replace"]),
        no_op=int(raw["noOp"]),
        remote_only=int(raw["remoteOnly"]),
        blocked=int(raw["blocked"]),
        operations=int(raw["operations"]),
    )
