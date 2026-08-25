"""Bounded apply/v3 payload materialization for Unified Catalog mutations."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from purview_governance.apply.errors import ApplyValidationError
from purview_governance.apply.models_v3 import ResourceTypeV3
from purview_governance.desired.models_v3 import (
    BusinessDomainDesiredState,
    DataProductDesiredState,
    DesiredStateV3,
    GlossaryTermDesiredState,
)
from purview_governance.plan.models_v3 import GovernancePlanV3, PlanAction, PlanOperationV3
from purview_governance.remote_state.business_domain_normalize import normalize_business_domain
from purview_governance.remote_state.data_product_normalize import normalize_data_product
from purview_governance.remote_state.data_product_policy import (
    DEFERRED_CONFIGURABLE_FIELDS as DP_DEFERRED,
)
from purview_governance.remote_state.glossary_term_normalize import normalize_glossary_term
from purview_governance.remote_state.glossary_term_policy import (
    DEFERRED_CONFIGURABLE_FIELDS as TERM_DEFERRED,
)
from purview_governance.remote_state.models_v3 import (
    NormalizedBusinessDomain,
    NormalizedDataProduct,
    NormalizedGlossaryTerm,
    RemoteStateV3,
)

PlanResourceTypeV3 = ResourceTypeV3
FreshDeferredIndex = dict[tuple[PlanResourceTypeV3, str], dict[str, str]]

BD_REPLACE_PRESERVED_FIELDS: frozenset[str] = frozenset(
    {"systemData", "thumbnail", "domains", "managedAttributes"},
)
FAILURE_SEMANTICS_UNVERIFIED = "apply.payload_semantics_unverified"
FAILURE_PREFLIGHT = "apply.payload_preflight_failed"


@dataclass(frozen=True, slots=True)
class MutationIntentV3:
    """Unified Catalog mutation intent for apply/v3."""

    sequence: int
    resource_type: PlanResourceTypeV3
    resource_id: str
    action: PlanAction
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class OperationPreflightRecord:
    """Targeted GET snapshot for one planned operation."""

    raw_get: dict[str, Any]
    deferred_fingerprints: dict[str, str]


@dataclass(frozen=True, slots=True)
class PreflightContext:
    """Per-operation preflight snapshots for payload materialization and TOCTOU."""

    plan: GovernancePlanV3
    fresh_deferred_index: FreshDeferredIndex
    by_sequence: dict[int, OperationPreflightRecord]


@dataclass(frozen=True, slots=True)
class VirtualExecutionStateV3:
    """Simulated post-create existence for dependency validation."""

    business_domain_ids: frozenset[str]
    data_product_ids: frozenset[str]
    glossary_term_ids: frozenset[str]

    @classmethod
    def from_fresh_remote(cls, fresh_remote: RemoteStateV3) -> VirtualExecutionStateV3:
        return cls(
            business_domain_ids=frozenset(item.id for item in fresh_remote.business_domains),
            data_product_ids=frozenset(item.id for item in fresh_remote.data_products),
            glossary_term_ids=frozenset(item.id for item in fresh_remote.glossary_terms),
        )

    def with_create(
        self,
        resource_type: PlanResourceTypeV3,
        resource_id: str,
    ) -> VirtualExecutionStateV3:
        if resource_type == "businessDomain":
            return VirtualExecutionStateV3(
                business_domain_ids=self.business_domain_ids | {resource_id},
                data_product_ids=self.data_product_ids,
                glossary_term_ids=self.glossary_term_ids,
            )
        if resource_type == "dataProduct":
            return VirtualExecutionStateV3(
                business_domain_ids=self.business_domain_ids,
                data_product_ids=self.data_product_ids | {resource_id},
                glossary_term_ids=self.glossary_term_ids,
            )
        return VirtualExecutionStateV3(
            business_domain_ids=self.business_domain_ids,
            data_product_ids=self.data_product_ids,
            glossary_term_ids=self.glossary_term_ids | {resource_id},
        )


def build_fresh_deferred_index(fresh_remote: RemoteStateV3) -> FreshDeferredIndex:
    """Index valueIdentity fingerprints from fresh global capture normalization."""
    index: FreshDeferredIndex = {}
    for domain in fresh_remote.business_domains:
        index[("businessDomain", domain.id)] = _unsupported_field_map(domain)
    for product in fresh_remote.data_products:
        index[("dataProduct", product.id)] = _unsupported_field_map(product)
    for term in fresh_remote.glossary_terms:
        index[("glossaryTerm", term.id)] = _unsupported_field_map(term)
    return index


def simulate_virtual_state(
    plan: GovernancePlanV3,
    fresh_remote: RemoteStateV3,
) -> VirtualExecutionStateV3:
    """Apply planned CREATE operations in sequence to a virtual existence set."""
    state = VirtualExecutionStateV3.from_fresh_remote(fresh_remote)
    for operation in sorted(plan.operations, key=lambda item: item.sequence):
        if operation.action == "create":
            state = state.with_create(operation.resource_type, operation.id)
    return state


def validate_operation_capability(
    operation: PlanOperationV3,
    plan: GovernancePlanV3,
    fresh_remote: RemoteStateV3,
    virtual_state: VirtualExecutionStateV3,
) -> str | None:
    """Return a failure code when apply/v3 cannot safely execute the operation."""
    desired = _desired_indexes(plan.desired_state)
    bd_create_ids = _business_domain_create_ids(plan)

    if operation.resource_type == "businessDomain":
        if operation.action == "create":
            return FAILURE_SEMANTICS_UNVERIFIED
        domain = desired.business_domains.get(operation.id)
        if domain is None:
            return FAILURE_PREFLIGHT
        remote = _find_business_domain(fresh_remote, operation.id)
        remote_parent = remote.properties.get("parentId") if remote is not None else None
        if domain.parent_id is None and remote_parent is not None:
            return FAILURE_SEMANTICS_UNVERIFIED
        if _business_domain_root_to_root_unsafe(domain, remote):
            return FAILURE_SEMANTICS_UNVERIFIED
        return None

    if operation.resource_type == "glossaryTerm":
        term = desired.glossary_terms.get(operation.id)
        if term is None:
            return FAILURE_PREFLIGHT
        if operation.action == "replace":
            remote = _find_glossary_term(fresh_remote, operation.id)
            remote_parent = remote.properties.get("parentId") if remote is not None else None
            if term.parent_id is None and remote_parent is not None:
                return FAILURE_SEMANTICS_UNVERIFIED
        return None

    if operation.resource_type == "dataProduct":
        product = desired.data_products.get(operation.id)
        if product is None:
            return FAILURE_PREFLIGHT
        if operation.action == "create" and product.domain in bd_create_ids:
            return FAILURE_SEMANTICS_UNVERIFIED
        if operation.action == "replace":
            remote = _find_data_product(fresh_remote, operation.id)
            if remote is not None and remote.properties.get("domain") != product.domain:
                return FAILURE_SEMANTICS_UNVERIFIED
        return None

    return FAILURE_PREFLIGHT


def check_plan_dependencies(
    plan: GovernancePlanV3,
    virtual_state: VirtualExecutionStateV3,
) -> str | None:
    """Validate cross-operation dependencies against simulated post-create existence."""
    desired = _desired_indexes(plan.desired_state)
    for operation in sorted(plan.operations, key=lambda item: item.sequence):
        if operation.resource_type == "dataProduct" and operation.action == "create":
            product = desired.data_products.get(operation.id)
            if product is None:
                return FAILURE_PREFLIGHT
            if product.domain not in virtual_state.business_domain_ids:
                return FAILURE_PREFLIGHT
        if operation.resource_type == "glossaryTerm" and operation.action == "create":
            term = desired.glossary_terms.get(operation.id)
            if term is None:
                return FAILURE_PREFLIGHT
            if term.parent_id is not None and term.parent_id not in virtual_state.glossary_term_ids:
                return FAILURE_PREFLIGHT
        if operation.action == "create":
            virtual_state = virtual_state.with_create(operation.resource_type, operation.id)
    return None


def bind_deferred_value_identities(
    raw_get: dict[str, Any],
    fresh_index: FreshDeferredIndex,
    resource_type: PlanResourceTypeV3,
) -> bool:
    """Return True when deferred-field valueIdentity fingerprints match fresh capture."""
    resource_id = raw_get.get("id")
    if not isinstance(resource_id, str):
        return False
    expected = fresh_index.get((resource_type, resource_id), {})
    actual = deferred_identities_from_raw(raw_get, resource_type)
    return actual == expected


def deferred_identities_from_raw(
    raw_get: dict[str, Any],
    resource_type: PlanResourceTypeV3,
) -> dict[str, str]:
    """Compute deferred-field valueIdentity map from a targeted GET body."""
    normalized = _normalize_raw(raw_get, resource_type)
    if normalized is None:
        return {}
    return _unsupported_field_map(normalized)


def materialize_mutation_intents_v3(
    plan: GovernancePlanV3,
    preflight_context: PreflightContext,
) -> tuple[MutationIntentV3, ...]:
    """Build POST/PUT payloads for every supported operation in the plan."""
    if preflight_context.plan is not plan:
        raise ApplyValidationError(
            FAILURE_PREFLIGHT,
            "preflight context plan mismatch",
        )

    desired = _desired_indexes(plan.desired_state)
    intents: list[MutationIntentV3] = []

    for operation in sorted(plan.operations, key=lambda item: item.sequence):
        record = preflight_context.by_sequence.get(operation.sequence)
        if operation.action == "replace" and record is None:
            raise ApplyValidationError(
                FAILURE_PREFLIGHT,
                "replace operation missing targeted GET preflight snapshot",
            )

        if operation.resource_type == "businessDomain":
            domain = desired.business_domains.get(operation.id)
            if domain is None:
                raise ApplyValidationError(
                    FAILURE_PREFLIGHT,
                    "planned businessDomain operation has no matching desired resource",
                )
            if operation.action != "replace":
                raise ApplyValidationError(
                    FAILURE_SEMANTICS_UNVERIFIED,
                    "businessDomain create is not supported by apply/v3",
                )
            raw_get = record.raw_get
            if _business_domain_raw_replace_unsafe(domain, raw_get):
                raise ApplyValidationError(
                    FAILURE_SEMANTICS_UNVERIFIED,
                    "businessDomain root replace cannot be satisfied from targeted GET",
                )
            if not bind_deferred_value_identities(
                raw_get,
                preflight_context.fresh_deferred_index,
                "businessDomain",
            ):
                raise ApplyValidationError(
                    FAILURE_PREFLIGHT,
                    "businessDomain deferred field fingerprints diverged from fresh capture",
                )
            payload = _materialize_business_domain_replace(domain, raw_get)
        elif operation.resource_type == "dataProduct":
            product = desired.data_products.get(operation.id)
            if product is None:
                raise ApplyValidationError(
                    FAILURE_PREFLIGHT,
                    "planned dataProduct operation has no matching desired resource",
                )
            if operation.action == "create":
                payload = _materialize_data_product_create(product)
            else:
                raw_get = record.raw_get
                if not bind_deferred_value_identities(
                    raw_get,
                    preflight_context.fresh_deferred_index,
                    "dataProduct",
                ):
                    raise ApplyValidationError(
                        FAILURE_PREFLIGHT,
                        "dataProduct deferred field fingerprints diverged from fresh capture",
                    )
                payload = _materialize_data_product_replace(product, raw_get)
        elif operation.resource_type == "glossaryTerm":
            term = desired.glossary_terms.get(operation.id)
            if term is None:
                raise ApplyValidationError(
                    FAILURE_PREFLIGHT,
                    "planned glossaryTerm operation has no matching desired resource",
                )
            if operation.action == "create":
                payload = _materialize_glossary_term_create(term)
            else:
                raw_get = record.raw_get
                remote_parent = raw_get.get("parentId")
                if term.parent_id is None and remote_parent is not None:
                    raise ApplyValidationError(
                        FAILURE_SEMANTICS_UNVERIFIED,
                        "glossaryTerm parent clear is not supported by apply/v3",
                    )
                if not bind_deferred_value_identities(
                    raw_get,
                    preflight_context.fresh_deferred_index,
                    "glossaryTerm",
                ):
                    raise ApplyValidationError(
                        FAILURE_PREFLIGHT,
                        "glossaryTerm deferred field fingerprints diverged from fresh capture",
                    )
                payload = _materialize_glossary_term_replace(term, raw_get)
        else:
            raise ApplyValidationError(
                FAILURE_PREFLIGHT,
                "plan contains unsupported mutation operations",
            )

        intents.append(
            MutationIntentV3(
                sequence=operation.sequence,
                resource_type=operation.resource_type,
                resource_id=operation.id,
                action=operation.action,
                payload=payload,
            )
        )

    return tuple(intents)


@dataclass(frozen=True, slots=True)
class _DesiredIndexes:
    business_domains: dict[str, BusinessDomainDesiredState]
    data_products: dict[str, DataProductDesiredState]
    glossary_terms: dict[str, GlossaryTermDesiredState]


def _desired_indexes(desired_state: DesiredStateV3) -> _DesiredIndexes:
    return _DesiredIndexes(
        business_domains={item.id: item for item in desired_state.business_domains},
        data_products={item.id: item for item in desired_state.data_products},
        glossary_terms={item.id: item for item in desired_state.glossary_terms},
    )


def _unsupported_field_map(
    normalized: NormalizedBusinessDomain | NormalizedDataProduct | NormalizedGlossaryTerm,
) -> dict[str, str]:
    return {
        field.path: field.value_identity for field in normalized.unsupported_configurable_fields
    }


def _normalize_raw(
    raw_get: dict[str, Any],
    resource_type: PlanResourceTypeV3,
) -> NormalizedBusinessDomain | NormalizedDataProduct | NormalizedGlossaryTerm | None:
    if resource_type == "businessDomain":
        result = normalize_business_domain(raw_get)
        return result if isinstance(result, NormalizedBusinessDomain) else None
    if resource_type == "dataProduct":
        result = normalize_data_product(raw_get)
        return result if isinstance(result, NormalizedDataProduct) else None
    result = normalize_glossary_term(raw_get)
    return result if isinstance(result, NormalizedGlossaryTerm) else None


def _find_business_domain(
    fresh_remote: RemoteStateV3,
    domain_id: str,
) -> NormalizedBusinessDomain | None:
    for item in fresh_remote.business_domains:
        if item.id == domain_id:
            return item
    return None


def _find_data_product(
    fresh_remote: RemoteStateV3,
    product_id: str,
) -> NormalizedDataProduct | None:
    for item in fresh_remote.data_products:
        if item.id == product_id:
            return item
    return None


def _find_glossary_term(
    fresh_remote: RemoteStateV3,
    term_id: str,
) -> NormalizedGlossaryTerm | None:
    for item in fresh_remote.glossary_terms:
        if item.id == term_id:
            return item
    return None


def _business_domain_create_ids(plan: GovernancePlanV3) -> frozenset[str]:
    return frozenset(
        operation.id
        for operation in plan.operations
        if operation.resource_type == "businessDomain" and operation.action == "create"
    )


def _business_domain_root_to_root_unsafe(
    desired: BusinessDomainDesiredState,
    remote: NormalizedBusinessDomain | None,
) -> bool:
    if desired.parent_id is not None:
        return False
    return not (remote is not None and "parentId" in remote.properties)


def _business_domain_raw_replace_unsafe(
    desired: BusinessDomainDesiredState,
    raw_get: dict[str, Any],
) -> bool:
    if desired.parent_id is not None:
        return False
    if raw_get.get("parentId") is not None:
        return False
    if "parentId" not in raw_get:
        return True
    return any(field not in raw_get for field in BD_REPLACE_PRESERVED_FIELDS)


def _materialize_business_domain_replace(
    desired: BusinessDomainDesiredState,
    raw_get: dict[str, Any],
) -> dict[str, Any]:
    payload = copy.deepcopy(raw_get)
    payload["id"] = desired.id
    payload["name"] = desired.name
    payload["status"] = desired.status
    payload["type"] = desired.domain_type
    if desired.description is not None:
        payload["description"] = desired.description
    elif "description" in payload:
        del payload["description"]
    if desired.parent_id is not None:
        payload["parentId"] = desired.parent_id
    elif "parentId" in payload:
        del payload["parentId"]
    if desired.is_restricted is not None:
        payload["isRestricted"] = desired.is_restricted
    # is_restricted None = unmanaged: keep raw_get value from deepcopy
    for field in BD_REPLACE_PRESERVED_FIELDS:
        if field in raw_get:
            payload[field] = copy.deepcopy(raw_get[field])
    return payload


def _materialize_data_product_create(desired: DataProductDesiredState) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": desired.id,
        "name": desired.name,
        "domain": desired.domain,
        "type": desired.product_type,
        "description": desired.description,
        "businessUse": desired.business_use,
        "status": "DRAFT",
        "contacts": {"owner": _owner_entries(desired.owners)},
    }
    if desired.audience is not None:
        payload["audience"] = list(desired.audience)
    if desired.update_frequency is not None:
        payload["updateFrequency"] = desired.update_frequency
    if desired.endorsed is not None:
        payload["endorsed"] = desired.endorsed
    return payload


def _materialize_data_product_replace(
    desired: DataProductDesiredState,
    raw_get: dict[str, Any],
) -> dict[str, Any]:
    payload = copy.deepcopy(raw_get)
    payload["id"] = desired.id
    payload["name"] = desired.name
    payload["domain"] = desired.domain
    payload["type"] = desired.product_type
    payload["description"] = desired.description
    payload["businessUse"] = desired.business_use
    payload["contacts"] = _merge_contacts(raw_get.get("contacts"), desired.owners)
    if desired.audience is not None:
        payload["audience"] = list(desired.audience)
    # audience None = unmanaged: keep raw_get value from deepcopy
    if desired.update_frequency is not None:
        payload["updateFrequency"] = desired.update_frequency
    # update_frequency None = unmanaged: keep raw_get value from deepcopy
    if desired.endorsed is not None:
        payload["endorsed"] = desired.endorsed
    # endorsed None = unmanaged: keep raw_get value from deepcopy
    for field in DP_DEFERRED:
        if field in raw_get:
            payload[field] = copy.deepcopy(raw_get[field])
    _preserve_deferred_contacts(payload, raw_get)
    if "systemData" in raw_get:
        payload["systemData"] = copy.deepcopy(raw_get["systemData"])
    return payload


def _materialize_glossary_term_create(desired: GlossaryTermDesiredState) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": desired.id,
        "name": desired.name,
        "domain": desired.domain,
        "description": desired.description,
        "status": "DRAFT",
        "contacts": {"owner": _owner_entries(desired.owners)},
    }
    if desired.parent_id is not None:
        payload["parentId"] = desired.parent_id
    if desired.acronyms is not None:
        payload["acronyms"] = list(desired.acronyms)
    return payload


def _materialize_glossary_term_replace(
    desired: GlossaryTermDesiredState,
    raw_get: dict[str, Any],
) -> dict[str, Any]:
    payload = copy.deepcopy(raw_get)
    payload["id"] = desired.id
    payload["name"] = desired.name
    payload["domain"] = desired.domain
    payload["description"] = desired.description
    payload["contacts"] = _merge_contacts(raw_get.get("contacts"), desired.owners)
    if desired.parent_id is not None:
        payload["parentId"] = desired.parent_id
    elif "parentId" in raw_get:
        payload["parentId"] = raw_get["parentId"]
    if desired.acronyms is not None:
        payload["acronyms"] = list(desired.acronyms)
    # acronyms None = unmanaged: keep raw_get value from deepcopy (PR4 three-state)
    for field in TERM_DEFERRED:
        if field in raw_get:
            payload[field] = copy.deepcopy(raw_get[field])
    _preserve_deferred_contacts(payload, raw_get)
    if "systemData" in raw_get:
        payload["systemData"] = copy.deepcopy(raw_get["systemData"])
    return payload


def _owner_entries(
    owners: tuple[Any, ...],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for owner in owners:
        entry: dict[str, Any] = {"id": owner.id}
        if owner.description is not None:
            entry["description"] = owner.description
        entries.append(entry)
    return entries


def _merge_contacts(
    raw_contacts: object,
    owners: tuple[Any, ...],
) -> dict[str, Any]:
    contacts = copy.deepcopy(raw_contacts) if isinstance(raw_contacts, dict) else {}
    contacts["owner"] = _owner_entries(owners)
    return contacts


def _preserve_deferred_contacts(payload: dict[str, Any], raw_get: dict[str, Any]) -> None:
    raw_contacts = raw_get.get("contacts")
    if not isinstance(raw_contacts, dict):
        return
    payload_contacts = payload.setdefault("contacts", {})
    if not isinstance(payload_contacts, dict):
        payload_contacts = {}
        payload["contacts"] = payload_contacts
    for role in ("expert", "databaseAdmin"):
        if role in raw_contacts:
            payload_contacts[role] = copy.deepcopy(raw_contacts[role])


__all__ = [
    "FreshDeferredIndex",
    "MutationIntentV3",
    "OperationPreflightRecord",
    "PreflightContext",
    "VirtualExecutionStateV3",
    "bind_deferred_value_identities",
    "build_fresh_deferred_index",
    "check_plan_dependencies",
    "deferred_identities_from_raw",
    "materialize_mutation_intents_v3",
    "simulate_virtual_state",
    "validate_operation_capability",
]
