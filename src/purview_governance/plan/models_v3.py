"""Frozen models for purview-governance-plan/v3."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from purview_governance.desired.models_v3 import DesiredStateV3
from purview_governance.diff.models import DiffDocument, DiffOutcome, DiffReason
from purview_governance.diff.models_v3 import DiffBusinessDomainItem
from purview_governance.plan.identity import (
    CONFIGURATION_API_VERSION_V3,
    PLAN_API_VERSION_V3,
    compute_plan_identity,
)
from purview_governance.remote_state.canonical import dumps_canonical

ExecutionEligibility = Literal["ready", "blocked"]
PlanAction = Literal["create", "replace"]
PlanResourceTypeV3 = Literal["businessDomain", "dataProduct", "glossaryTerm"]


@dataclass(frozen=True, slots=True)
class PlanTargetContextV3:
    surface: Literal["unifiedCatalog"]
    tenant_id: str
    endpoint: str
    identity: str

    def to_document(self) -> dict[str, str]:
        return {
            "surface": self.surface,
            "tenantId": self.tenant_id,
            "endpoint": self.endpoint,
            "identity": self.identity,
        }


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
class PlanOperationV3:
    sequence: int
    resource_type: PlanResourceTypeV3
    id: str
    action: PlanAction

    def to_document(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "id": self.id,
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
class GovernancePlanV3:
    """Versioned purview-governance-plan/v3 artifact model."""

    api_version: str
    configuration_api_version: str
    target_context: PlanTargetContextV3
    identities: PlanIdentities
    desired_state: DesiredStateV3
    change_set: DiffDocument
    execution_eligibility: ExecutionEligibility
    operations: tuple[PlanOperationV3, ...]
    summary: PlanSummary
    plan_identity: str

    def to_document(self) -> dict[str, Any]:
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
        from purview_governance.plan.validation_v3 import (
            validate_plan_document_for_serialization_v3,
        )

        document = self.to_document()
        validate_plan_document_for_serialization_v3(document)
        return dumps_canonical(document)


def build_plan_from_parts_v3(
    *,
    target_context: PlanTargetContextV3,
    identities: PlanIdentities,
    desired_state: DesiredStateV3,
    change_set: DiffDocument,
    execution_eligibility: ExecutionEligibility,
    operations: tuple[PlanOperationV3, ...],
    summary: PlanSummary,
) -> GovernancePlanV3:
    """Assemble a plan/v3 and compute ``planIdentity`` (caller must self-validate afterward)."""
    provisional = GovernancePlanV3(
        api_version=PLAN_API_VERSION_V3,
        configuration_api_version=CONFIGURATION_API_VERSION_V3,
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
    return GovernancePlanV3(
        api_version=PLAN_API_VERSION_V3,
        configuration_api_version=CONFIGURATION_API_VERSION_V3,
        target_context=target_context,
        identities=identities,
        desired_state=desired_state,
        change_set=change_set,
        execution_eligibility=execution_eligibility,
        operations=operations,
        summary=summary,
        plan_identity=plan_identity,
    )


def desired_state_v3_from_document(document: dict[str, Any]) -> DesiredStateV3:
    from purview_governance.desired.models_v3 import (
        BusinessDomainDesiredState,
        DataProductDesiredState,
        DataProductOwnerDesiredState,
        GlossaryTermDesiredState,
        GlossaryTermOwnerDesiredState,
    )

    domains: list[BusinessDomainDesiredState] = []
    for raw in document.get("businessDomains", []):
        props = raw["properties"]
        domains.append(
            BusinessDomainDesiredState(
                id=raw["id"],
                name=props["name"],
                description=props.get("description"),
                parent_id=props.get("parentId"),
                status=props["status"],
                domain_type=props["type"],
                is_restricted=props.get("isRestricted"),
            )
        )

    products: list[DataProductDesiredState] = []
    for raw in document.get("dataProducts", []):
        props = raw["properties"]
        owners = tuple(
            DataProductOwnerDesiredState(
                id=owner["id"],
                description=owner.get("description"),
            )
            for owner in props["owners"]
        )
        audience_raw = props.get("audience")
        audience = tuple(audience_raw) if audience_raw is not None else None
        products.append(
            DataProductDesiredState(
                id=raw["id"],
                name=props["name"],
                domain=props["domain"],
                product_type=props["type"],
                description=props["description"],
                business_use=props["businessUse"],
                owners=owners,
                audience=audience,  # type: ignore[arg-type]
                update_frequency=props.get("updateFrequency"),
                endorsed=props.get("endorsed"),
            )
        )

    terms: list[GlossaryTermDesiredState] = []
    for raw in document.get("glossaryTerms", []):
        props = raw["properties"]
        owners = tuple(
            GlossaryTermOwnerDesiredState(
                id=owner["id"],
                description=owner.get("description"),
            )
            for owner in props["owners"]
        )
        acronyms: tuple[str, ...] | None = None
        if "acronyms" in props:
            acronyms = tuple(props["acronyms"])
        terms.append(
            GlossaryTermDesiredState(
                id=raw["id"],
                name=props["name"],
                domain=props["domain"],
                description=props["description"],
                owners=owners,
                parent_id=props.get("parentId"),
                acronyms=acronyms,
            )
        )

    return DesiredStateV3(
        business_domains=tuple(domains),
        data_products=tuple(products),
        glossary_terms=tuple(terms),
    )


def change_set_v3_from_document(document: dict[str, Any]) -> DiffDocument:
    from purview_governance.diff.models_v3 import DiffDataProductItem, DiffGlossaryTermItem

    items: list[DiffBusinessDomainItem | DiffDataProductItem | DiffGlossaryTermItem] = []
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
        resource_type = raw["type"]
        if resource_type == "dataProduct":
            items.append(
                DiffDataProductItem(
                    id=raw["id"],
                    resource_type="dataProduct",
                    outcome=outcome,
                    reasons=reasons,
                )
            )
        elif resource_type == "glossaryTerm":
            items.append(
                DiffGlossaryTermItem(
                    id=raw["id"],
                    resource_type="glossaryTerm",
                    outcome=outcome,
                    reasons=reasons,
                )
            )
        else:
            items.append(
                DiffBusinessDomainItem(
                    id=raw["id"],
                    resource_type="businessDomain",
                    outcome=outcome,
                    reasons=reasons,
                )
            )
    return DiffDocument(items=tuple(items))


def operations_v3_from_document(
    raw_operations: list[dict[str, Any]],
) -> tuple[PlanOperationV3, ...]:
    return tuple(
        PlanOperationV3(
            sequence=int(item["sequence"]),
            resource_type=item["type"],
            id=item["id"],
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
