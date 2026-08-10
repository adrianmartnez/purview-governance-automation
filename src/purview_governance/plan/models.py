"""Frozen models for purview-governance-plan/v1 and /v2."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from purview_governance.desired.models import (
    DataSourceDesiredState,
    DesiredState,
    ScanDesiredState,
    ScanRuleSetDesiredState,
)
from purview_governance.diff.models import DiffDocument, DiffItem, DiffOutcome, DiffReason
from purview_governance.plan.identity import (
    CONFIGURATION_API_VERSION,
    PLAN_API_VERSION,
    PLAN_API_VERSION_V2,
    compute_plan_identity,
)
from purview_governance.remote_state.canonical import dumps_canonical

ExecutionEligibility = Literal["ready", "blocked"]
PlanAction = Literal["create", "replace"]
PlanResourceType = Literal["dataSource", "scan", "scanRuleSet"]


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
    resource_type: PlanResourceType
    name: str
    action: PlanAction
    data_source_name: str | None = None

    def to_document(self) -> dict[str, Any]:
        doc: dict[str, Any] = {
            "action": self.action,
            "name": self.name,
            "sequence": self.sequence,
            "type": self.resource_type,
        }
        if self.resource_type == "scan":
            doc["dataSourceName"] = self.data_source_name
        return doc


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
    """Versioned purview-governance-plan artifact model (v1 or v2)."""

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
        multi_resource = self.api_version.endswith("/v2")
        return {
            "apiVersion": self.api_version,
            "changeSet": self.change_set.to_document(),
            "configurationApiVersion": self.configuration_api_version,
            "desiredState": self.desired_state.to_document(multi_resource=multi_resource),
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
    """Assemble a plan/v1 and compute ``planIdentity`` (caller must self-validate afterward)."""
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


def build_plan_from_parts_v2(
    *,
    configuration_api_version: str,
    target_context: PlanTargetContext,
    identities: PlanIdentities,
    desired_state: DesiredState,
    change_set: DiffDocument,
    execution_eligibility: ExecutionEligibility,
    operations: tuple[PlanOperation, ...],
    summary: PlanSummary,
) -> GovernancePlan:
    """Assemble a plan/v2 and compute ``planIdentity`` (caller must self-validate afterward)."""
    provisional = GovernancePlan(
        api_version=PLAN_API_VERSION_V2,
        configuration_api_version=configuration_api_version,
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
        api_version=PLAN_API_VERSION_V2,
        configuration_api_version=configuration_api_version,
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
    data_sources: list[DataSourceDesiredState] = []
    for raw in document.get("dataSources", []):
        props = raw["properties"]
        data_sources.append(
            DataSourceDesiredState(
                name=raw["name"],
                kind="AzureStorage",
                endpoint=props["endpoint"],
                collection_reference_name=props["collection"]["referenceName"],
            )
        )

    scan_rule_sets: list[ScanRuleSetDesiredState] = []
    for raw in document.get("scanRuleSets", []):
        props = raw["properties"]
        scan_rule_sets.append(
            ScanRuleSetDesiredState(
                name=raw["name"],
                kind="AzureStorage",
                scan_ruleset_type="Custom",
                file_extensions=tuple(props["scanningRule"]["fileExtensions"]),
                excluded_system_classifications=tuple(props["excludedSystemClassifications"]),
                included_custom_classification_rule_names=tuple(
                    props["includedCustomClassificationRuleNames"]
                ),
                description=props.get("description"),
            )
        )

    scans: list[ScanDesiredState] = []
    for raw in document.get("scans", []):
        props = raw["properties"]
        scans.append(
            ScanDesiredState(
                name=raw["name"],
                kind="AzureStorageMsi",
                data_source_name=props["dataSourceName"],
                scan_ruleset_name=props["scanRulesetName"],
                scan_ruleset_type=props["scanRulesetType"],
                collection_reference_name=props["collection"]["referenceName"],
            )
        )

    return DesiredState(
        data_sources=tuple(data_sources),
        scan_rule_sets=tuple(scan_rule_sets),
        scans=tuple(scans),
    )


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
        resource_type = raw.get("type", "dataSource")
        items.append(
            DiffItem(
                name=raw["name"],
                resource_type=resource_type,
                outcome=outcome,
                reasons=reasons,
                data_source_name=raw.get("dataSourceName"),
            )
        )
    return DiffDocument(items=tuple(items))


def operations_from_document(raw_operations: list[dict[str, Any]]) -> tuple[PlanOperation, ...]:
    return tuple(
        PlanOperation(
            sequence=int(item["sequence"]),
            resource_type=item.get("type", "dataSource"),
            name=item["name"],
            action=item["action"],
            data_source_name=item.get("dataSourceName"),
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
