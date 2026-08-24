"""Semantic validation for purview-governance-plan/v3."""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator

from purview_governance.config.diagnostics import ConfigValidationError
from purview_governance.config.models_v3 import GovernanceConfigV3
from purview_governance.config.validate_v3 import validate_document_v3
from purview_governance.plan.errors import (
    PlanBuildError,
    PlanIntegrityError,
    PlanSchemaError,
)
from purview_governance.plan.identity import (
    CONFIGURATION_API_VERSION_V3,
    PLAN_API_VERSION_V3,
    compute_desired_state_identity,
    compute_material_configuration_identity,
    compute_plan_identity,
    compute_target_context_identity_v3,
    is_sha256_identity,
)
from purview_governance.plan.schema import load_plan_v3_schema
from purview_governance.remote_state.canonical import (
    compute_material_state_identity,
    dumps_canonical,
)
from purview_governance.remote_state.models_v3 import RemoteStateV3
from purview_governance.remote_state.schema import load_remote_state_v3_schema
from purview_governance.uuid_utils import normalize_uuid_string

BUSINESS_DOMAIN_REPLACE_REASON_CODES = frozenset(
    {
        "properties.name.changed",
        "properties.description.changed",
        "properties.parentId.changed",
        "properties.status.changed",
        "properties.type.changed",
        "properties.isRestricted.changed",
    }
)

DATA_PRODUCT_REPLACE_REASON_CODES = frozenset(
    {
        "properties.name.changed",
        "properties.domain.changed",
        "properties.type.changed",
        "properties.description.changed",
        "properties.businessUse.changed",
        "properties.owners.changed",
        "properties.audience.changed",
        "properties.updateFrequency.changed",
        "properties.endorsed.changed",
    }
)

GLOSSARY_TERM_REPLACE_REASON_CODES = frozenset(
    {
        "properties.name.changed",
        "properties.domain.changed",
        "properties.description.changed",
        "properties.owners.changed",
        "properties.parentId.changed",
        "properties.acronyms.changed",
    }
)

MATERIAL_REPLACE_REASON_CODES = (
    BUSINESS_DOMAIN_REPLACE_REASON_CODES
    | DATA_PRODUCT_REPLACE_REASON_CODES
    | GLOSSARY_TERM_REPLACE_REASON_CODES
)

BLOCKING_REASON_CODES_V3 = frozenset(
    {
        "remote.unsupported_configurable_field",
        "remote.business_domain_name_conflict",
        "remote.status_blocks_replace",
        "remote_state.hierarchy_ambiguous",
        "plan.domain_move_unverified",
        "plan.domain_dependency_blocked",
        "plan.domain_unresolved",
        "plan.domain_uninterpreted",
        "plan.remote_capture_incomplete",
        "plan.glossary_term_domain_move_unverified",
        "plan.glossary_term_parent_domain_mismatch",
        "plan.glossary_term_parent_unresolved",
        "plan.glossary_term_parent_uninterpreted",
        "plan.glossary_term_parent_dependency_blocked",
        "plan.glossary_term_hierarchy_cycle",
    }
)

REASON_PATHS_V3: dict[str, str | None] = {
    "desired.absent_remote": "/",
    "remote.absent_desired": "/",
    "remote.unsupported_configurable_field": None,
    "remote.business_domain_name_conflict": "/properties/name",
    "remote.status_blocks_replace": "/safetyProperties/status",
    "remote_state.hierarchy_ambiguous": "/",
    "plan.domain_move_unverified": "/properties/domain",
    "plan.domain_dependency_blocked": "/properties/domain",
    "plan.domain_unresolved": "/properties/domain",
    "plan.domain_uninterpreted": "/properties/domain",
    "plan.remote_capture_incomplete": "/",
    "plan.glossary_term_domain_move_unverified": "/properties/domain",
    "plan.glossary_term_parent_domain_mismatch": "/properties/parentId",
    "plan.glossary_term_parent_unresolved": "/properties/parentId",
    "plan.glossary_term_parent_uninterpreted": "/properties/parentId",
    "plan.glossary_term_parent_dependency_blocked": "/properties/parentId",
    "plan.glossary_term_hierarchy_cycle": "/properties/parentId",
    "properties.name.changed": "/properties/name",
    "properties.description.changed": "/properties/description",
    "properties.parentId.changed": "/properties/parentId",
    "properties.status.changed": "/properties/status",
    "properties.type.changed": "/properties/type",
    "properties.isRestricted.changed": "/properties/isRestricted",
    "properties.domain.changed": "/properties/domain",
    "properties.businessUse.changed": "/properties/businessUse",
    "properties.owners.changed": "/properties/owners",
    "properties.audience.changed": "/properties/audience",
    "properties.updateFrequency.changed": "/properties/updateFrequency",
    "properties.endorsed.changed": "/properties/endorsed",
    "properties.acronyms.changed": "/properties/acronyms",
}

NO_BEFORE_AFTER_CODES_V3 = frozenset(
    {
        "desired.absent_remote",
        "remote.absent_desired",
        "remote.unsupported_configurable_field",
        "remote_state.hierarchy_ambiguous",
        "plan.domain_move_unverified",
        "plan.domain_dependency_blocked",
        "plan.domain_unresolved",
        "plan.domain_uninterpreted",
        "plan.remote_capture_incomplete",
        "plan.glossary_term_domain_move_unverified",
        "plan.glossary_term_parent_domain_mismatch",
        "plan.glossary_term_parent_unresolved",
        "plan.glossary_term_parent_uninterpreted",
        "plan.glossary_term_parent_dependency_blocked",
        "plan.glossary_term_hierarchy_cycle",
    }
)


def _integrity(code: str, message: str, *, path: str = "") -> PlanIntegrityError:
    return PlanIntegrityError(code, message, path=path)


def _raise_integrity(code: str, message: str, *, path: str = "") -> None:
    raise _integrity(code, message, path=path)


def validate_governance_config_for_planning_v3(config: GovernanceConfigV3) -> None:
    """Revalidate a public GovernanceConfigV3 for planning."""
    document_failed = False
    document: dict[str, Any] | None = None
    try:
        document = config.to_document()
    except Exception:
        document_failed = True
    if document_failed or document is None:
        raise PlanBuildError(
            "plan.invalid_configuration_input",
            "governance configuration input could not be serialized",
        )

    config_invalid = False
    try:
        validate_document_v3(document)
    except ConfigValidationError:
        config_invalid = True
    except Exception:
        config_invalid = True
    if config_invalid:
        raise PlanBuildError(
            "plan.invalid_configuration_input",
            "governance configuration input failed contract validation",
        )

    if config.target.surface != "unifiedCatalog":
        raise PlanBuildError(
            "plan.invalid_configuration_input",
            "governance configuration target surface must be unifiedCatalog",
            path="/target/surface",
        )
    if normalize_uuid_string(config.target.tenant_id) is None:
        raise PlanBuildError(
            "plan.invalid_configuration_input",
            "governance configuration target tenantId must be a valid UUID",
            path="/target/tenantId",
        )


def validate_remote_state_for_planning_v3(remote_state: RemoteStateV3) -> None:
    """Validate RemoteStateV3 as canonical purview-remote-state/v3 planning input."""
    document_failed = False
    document: dict[str, Any] | None = None
    try:
        document = remote_state.to_document()
    except Exception:
        document_failed = True
    if document_failed or document is None:
        raise PlanBuildError(
            "plan.invalid_remote_state_input",
            "remote state input could not be serialized",
        )

    schema_failed = False
    try:
        schema = load_remote_state_v3_schema()
        Draft202012Validator(schema).validate(document)
    except Exception:
        schema_failed = True
    if schema_failed:
        raise PlanBuildError(
            "plan.invalid_remote_state_input",
            "remote state input failed schema validation",
        )

    domain_ids = [item.id for item in remote_state.business_domains]
    if domain_ids != sorted(domain_ids):
        raise PlanBuildError(
            "plan.invalid_remote_state_input",
            "remote businessDomains must be sorted by id",
            path="/businessDomains",
        )

    uninterpreted_ids = [
        item.id for item in remote_state.uninterpreted_business_domains if item.id is not None
    ]
    if uninterpreted_ids != sorted(uninterpreted_ids):
        raise PlanBuildError(
            "plan.invalid_remote_state_input",
            "remote uninterpretedBusinessDomains ids must be sorted",
            path="/uninterpretedBusinessDomains",
        )

    seen: set[str] = set()
    for item in remote_state.business_domains:
        if item.id in seen:
            raise PlanBuildError(
                "plan.invalid_remote_state_input",
                "remote businessDomains ids must be unique",
                path="/businessDomains",
            )
        seen.add(item.id)
    for item in remote_state.uninterpreted_business_domains:
        if item.id is None:
            continue
        if item.id in seen:
            raise PlanBuildError(
                "plan.invalid_remote_state_input",
                "remote uninterpretedBusinessDomains ids must not overlap businessDomains",
                path="/uninterpretedBusinessDomains",
            )
        seen.add(item.id)

    identity_doc_failed = False
    expected = ""
    try:
        expected = compute_material_state_identity(remote_state.identity_document())
    except Exception:
        identity_doc_failed = True
    if identity_doc_failed:
        raise PlanBuildError(
            "plan.invalid_remote_state_input",
            "remote state identity document is invalid",
        )
    if expected != remote_state.material_state_identity:
        raise PlanBuildError(
            "plan.inconsistent_remote_identity",
            "remote materialStateIdentity does not match recomputed identity",
        )

    target = remote_state.target_context
    target_identity_failed = False
    expected_target = ""
    try:
        expected_target = compute_target_context_identity_v3(
            surface=target.surface,
            tenant_id=target.tenant_id,
            endpoint=target.endpoint,
        )
    except Exception:
        target_identity_failed = True
    if target_identity_failed or expected_target != target.identity:
        raise PlanBuildError(
            "plan.inconsistent_remote_identity",
            "remote targetContext.identity does not match recomputed identity",
        )


def _validate_reason_shape_v3(reason: dict[str, Any], *, path: str) -> None:
    code = reason.get("code")
    reason_path = reason.get("path")
    if not isinstance(code, str) or (
        code not in REASON_PATHS_V3 and not code.startswith("remote_state.")
    ):
        _raise_integrity("plan.invalid_reason", "unknown or unsupported reason code", path=path)

    expected_path = REASON_PATHS_V3.get(code)
    if expected_path is None and code.startswith("remote_state."):
        expected_path = "/"
    if expected_path is None:
        if (
            not isinstance(reason_path, str)
            or not reason_path.startswith("/")
            or len(reason_path) < 2
        ):
            _raise_integrity(
                "plan.invalid_reason",
                "reason path must be a non-empty JSON pointer",
                path=path,
            )
    elif reason_path != expected_path:
        _raise_integrity("plan.invalid_reason", "reason path does not match code", path=path)

    has_before = "before" in reason
    has_after = "after" in reason
    before = reason.get("before")
    after = reason.get("after")

    if code in NO_BEFORE_AFTER_CODES_V3:
        if has_before or has_after:
            _raise_integrity("plan.invalid_reason", "reason forbids before/after", path=path)
        return

    if code == "remote.business_domain_name_conflict":
        if not has_before or has_after:
            _raise_integrity(
                "plan.invalid_reason",
                "name conflict reason requires before and forbids after",
                path=path,
            )
        if not isinstance(before, str) or not before:
            _raise_integrity(
                "plan.invalid_reason",
                "name conflict before must be a non-empty string",
                path=path,
            )
        return

    if code == "remote.status_blocks_replace":
        if not has_before or has_after:
            _raise_integrity(
                "plan.invalid_reason",
                "status blocks replace reason requires before and forbids after",
                path=path,
            )
        if not isinstance(before, str) or not before:
            _raise_integrity(
                "plan.invalid_reason",
                "status blocks replace before must be a non-empty string",
                path=path,
            )
        return

    if code in MATERIAL_REPLACE_REASON_CODES:
        if not has_before or not has_after:
            _raise_integrity(
                "plan.invalid_reason",
                "material change reason requires before and after",
                path=path,
            )
        if not isinstance(before, str) or not isinstance(after, str):
            _raise_integrity(
                "plan.invalid_reason",
                "material change before/after must be strings",
                path=path,
            )
        if before == after:
            _raise_integrity(
                "plan.invalid_reason",
                "material change before and after must differ",
                path=path,
            )
        return

    if code.startswith("remote_state.") or code.startswith("plan."):
        return

    _raise_integrity("plan.invalid_reason", "unsupported reason code", path=path)


def _reason_codes(reasons: list[dict[str, Any]]) -> list[str]:
    return [str(item["code"]) for item in reasons]


def _desired_lookup(desired_state: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    lookup: dict[tuple[str, str], dict[str, Any]] = {}
    for item in desired_state.get("businessDomains", []):
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            lookup[("businessDomain", item["id"])] = item
    for item in desired_state.get("dataProducts", []):
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            lookup[("dataProduct", item["id"])] = item
    for item in desired_state.get("glossaryTerms", []):
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            lookup[("glossaryTerm", item["id"])] = item
    return lookup


def _bind_reason_after_to_desired_v3(
    reasons: list[dict[str, Any]],
    desired: dict[str, Any] | None,
    *,
    path: str,
) -> None:
    if desired is None:
        return
    props = desired["properties"]
    for index, reason_item in enumerate(reasons):
        code = reason_item["code"]
        reason_path = f"{path}/reasons/{index}"
        if code == "properties.name.changed":
            if reason_item.get("after") != props["name"]:
                _raise_integrity(
                    "plan.invalid_reason_outcome",
                    "name reason after must equal desired name",
                    path=reason_path,
                )
        elif code == "properties.description.changed":
            desired_desc = props.get("description")
            if reason_item.get("after") != dumps_canonical_value_scalar(desired_desc):
                _raise_integrity(
                    "plan.invalid_reason_outcome",
                    "description reason after must equal desired description",
                    path=reason_path,
                )
        elif code == "properties.parentId.changed":
            desired_parent = props.get("parentId")
            if reason_item.get("after") != dumps_canonical_value_scalar(desired_parent):
                _raise_integrity(
                    "plan.invalid_reason_outcome",
                    "parentId reason after must equal desired parentId",
                    path=reason_path,
                )
        elif code == "properties.status.changed":
            if reason_item.get("after") != props["status"]:
                _raise_integrity(
                    "plan.invalid_reason_outcome",
                    "status reason after must equal desired status",
                    path=reason_path,
                )
        elif code == "properties.type.changed":
            if reason_item.get("after") != props["type"]:
                _raise_integrity(
                    "plan.invalid_reason_outcome",
                    "type reason after must equal desired type",
                    path=reason_path,
                )
        elif code == "properties.isRestricted.changed":
            desired_restricted = props.get("isRestricted")
            if reason_item.get("after") != dumps_canonical_value_scalar(desired_restricted):
                _raise_integrity(
                    "plan.invalid_reason_outcome",
                    "isRestricted reason after must equal desired isRestricted",
                    path=reason_path,
                )
        elif code == "properties.domain.changed":
            if reason_item.get("after") != props["domain"]:
                _raise_integrity(
                    "plan.invalid_reason_outcome",
                    "domain reason after must equal desired domain",
                    path=reason_path,
                )
        elif code == "properties.businessUse.changed":
            if reason_item.get("after") != props["businessUse"]:
                _raise_integrity(
                    "plan.invalid_reason_outcome",
                    "businessUse reason after must equal desired businessUse",
                    path=reason_path,
                )
        elif code == "properties.owners.changed":
            if reason_item.get("after") != dumps_canonical_value_scalar(props["owners"]):
                _raise_integrity(
                    "plan.invalid_reason_outcome",
                    "owners reason after must equal desired owners",
                    path=reason_path,
                )
        elif code == "properties.audience.changed":
            desired_audience = props.get("audience")
            if reason_item.get("after") != dumps_canonical_value_scalar(desired_audience):
                _raise_integrity(
                    "plan.invalid_reason_outcome",
                    "audience reason after must equal desired audience",
                    path=reason_path,
                )
        elif code == "properties.updateFrequency.changed":
            desired_frequency = props.get("updateFrequency")
            if reason_item.get("after") != dumps_canonical_value_scalar(desired_frequency):
                _raise_integrity(
                    "plan.invalid_reason_outcome",
                    "updateFrequency reason after must equal desired updateFrequency",
                    path=reason_path,
                )
        elif code == "properties.endorsed.changed":
            desired_endorsed = props.get("endorsed")
            if reason_item.get("after") != dumps_canonical_value_scalar(desired_endorsed):
                _raise_integrity(
                    "plan.invalid_reason_outcome",
                    "endorsed reason after must equal desired endorsed",
                    path=reason_path,
                )
        elif code == "properties.acronyms.changed":
            desired_acronyms = props.get("acronyms")
            if reason_item.get("after") != dumps_canonical_value_scalar(desired_acronyms):
                _raise_integrity(
                    "plan.invalid_reason_outcome",
                    "acronyms reason after must equal desired acronyms",
                    path=reason_path,
                )


def dumps_canonical_value_scalar(value: object) -> str:
    from purview_governance.remote_state.canonical import dumps_canonical_value

    return dumps_canonical_value(value)


def _validate_outcome_reasons_v3(
    *,
    resource_type: str,
    outcome: str,
    reasons: list[dict[str, Any]],
    has_desired: bool,
    desired: dict[str, Any] | None,
    path: str,
) -> None:
    codes = _reason_codes(reasons)
    _bind_reason_after_to_desired_v3(reasons, desired, path=path)

    replace_codes = (
        BUSINESS_DOMAIN_REPLACE_REASON_CODES
        if resource_type == "businessDomain"
        else GLOSSARY_TERM_REPLACE_REASON_CODES
        if resource_type == "glossaryTerm"
        else DATA_PRODUCT_REPLACE_REASON_CODES
    )

    if outcome == "create":
        if not has_desired:
            _raise_integrity(
                "plan.invalid_membership", "create requires desired resource", path=path
            )
        if codes != ["desired.absent_remote"]:
            _raise_integrity(
                "plan.invalid_reason_outcome",
                "create reasons must be exactly desired.absent_remote",
                path=path,
            )
        return

    if outcome == "replace":
        if not has_desired:
            _raise_integrity(
                "plan.invalid_membership", "replace requires desired resource", path=path
            )
        if not codes or not all(code in replace_codes for code in codes):
            _raise_integrity(
                "plan.invalid_reason_outcome",
                "replace reasons must be property change codes only",
                path=path,
            )
        if any(code in BLOCKING_REASON_CODES_V3 for code in codes):
            _raise_integrity(
                "plan.invalid_reason_outcome",
                "replace must not include blocking reason codes",
                path=path,
            )
        return

    if outcome == "no-op":
        if not has_desired:
            _raise_integrity(
                "plan.invalid_membership", "no-op requires desired resource", path=path
            )
        if reasons:
            _raise_integrity(
                "plan.invalid_reason_outcome",
                "no-op reasons must be empty",
                path=path,
            )
        return

    if outcome == "remote-only":
        if has_desired:
            _raise_integrity(
                "plan.invalid_membership",
                "remote-only must not have a desired resource",
                path=path,
            )
        if "remote.absent_desired" not in codes:
            _raise_integrity(
                "plan.invalid_reason_outcome",
                "remote-only must include remote.absent_desired",
                path=path,
            )
        allowed = BLOCKING_REASON_CODES_V3 | {"remote.absent_desired"}
        if any(code not in allowed for code in codes):
            _raise_integrity(
                "plan.invalid_reason_outcome",
                "remote-only contains disallowed reason codes",
                path=path,
            )
        return

    if outcome == "blocked":
        if not reasons:
            _raise_integrity(
                "plan.invalid_reason_outcome",
                "blocked item must include at least one reason",
                path=path,
            )
        if not any(
            code in BLOCKING_REASON_CODES_V3
            or code.startswith("remote_state.")
            or code.startswith("plan.")
            for code in codes
        ):
            _raise_integrity(
                "plan.invalid_reason_outcome",
                "blocked item must include a blocking reason",
                path=path,
            )
        return

    _raise_integrity("plan.invalid_reason_outcome", "unsupported outcome", path=path)


def _topological_create_ids(
    create_ids: list[str],
    parent_by_id: dict[str, str | None],
) -> list[str]:
    create_set = set(create_ids)
    ordered: list[str] = []
    placed: set[str] = set()
    remaining = list(create_ids)
    while remaining:
        progress = False
        next_remaining: list[str] = []
        for domain_id in remaining:
            parent = parent_by_id.get(domain_id)
            if parent is None or parent not in create_set or parent in placed:
                ordered.append(domain_id)
                placed.add(domain_id)
                progress = True
            else:
                next_remaining.append(domain_id)
        if not progress:
            _raise_integrity(
                "plan.invalid_operation_mapping",
                "create operations cannot be topologically ordered",
                path="/operations",
            )
        remaining = next_remaining
    return ordered


def validate_plan_document_semantics_v3(document: dict[str, Any]) -> None:
    if document.get("apiVersion") != PLAN_API_VERSION_V3:
        _raise_integrity(
            "plan.unsupported_version",
            "plan document apiVersion must be purview-governance-plan/v3",
            path="/apiVersion",
        )
    if document.get("configurationApiVersion") != CONFIGURATION_API_VERSION_V3:
        _raise_integrity(
            "plan.invalid_schema",
            "configurationApiVersion must be purview-governance-config/v3",
            path="/configurationApiVersion",
        )

    target = document.get("targetContext")
    if not isinstance(target, dict):
        _raise_integrity(
            "plan.invalid_schema", "targetContext must be an object", path="/targetContext"
        )
    tenant_id = target.get("tenantId")
    if normalize_uuid_string(tenant_id) is None:
        _raise_integrity(
            "plan.noncanonical_input",
            "targetContext.tenantId must be a valid UUID",
            path="/targetContext/tenantId",
        )
    endpoint = target.get("endpoint")
    if not isinstance(endpoint, str) or not endpoint.strip():
        _raise_integrity(
            "plan.noncanonical_input",
            "targetContext.endpoint must be a non-empty string",
            path="/targetContext/endpoint",
        )
    target_identity = target.get("identity")
    if not is_sha256_identity(target_identity):
        _raise_integrity(
            "plan.noncanonical_input",
            "targetContext.identity must be sha256",
            path="/targetContext/identity",
        )
    expected_target = compute_target_context_identity_v3(
        surface=str(target.get("surface")),
        tenant_id=str(tenant_id),
        endpoint=str(endpoint),
    )
    if target_identity != expected_target:
        _raise_integrity(
            "plan.identity_mismatch",
            "targetContext.identity mismatch",
            path="/targetContext/identity",
        )

    identities = document.get("identities")
    if not isinstance(identities, dict):
        _raise_integrity("plan.invalid_schema", "identities must be an object", path="/identities")
    for key in ("desiredState", "materialConfiguration", "remoteState"):
        if not is_sha256_identity(identities.get(key)):
            _raise_integrity(
                "plan.noncanonical_input",
                f"identities.{key} must be sha256",
                path=f"/identities/{key}",
            )

    desired_state = document.get("desiredState")
    if not isinstance(desired_state, dict):
        _raise_integrity(
            "plan.invalid_schema", "desiredState must be an object", path="/desiredState"
        )
    expected_desired = compute_desired_state_identity(desired_state)
    if identities.get("desiredState") != expected_desired:
        _raise_integrity(
            "plan.identity_mismatch",
            "identities.desiredState mismatch",
            path="/identities/desiredState",
        )
    expected_material = compute_material_configuration_identity(
        target_context_identity=str(target_identity),
        desired_state_identity=expected_desired,
        configuration_api_version=CONFIGURATION_API_VERSION_V3,
    )
    if identities.get("materialConfiguration") != expected_material:
        _raise_integrity(
            "plan.identity_mismatch",
            "identities.materialConfiguration mismatch",
            path="/identities/materialConfiguration",
        )

    desired_lookup = _desired_lookup(desired_state)
    change_set = document.get("changeSet")
    if not isinstance(change_set, dict):
        _raise_integrity("plan.invalid_schema", "changeSet must be an object", path="/changeSet")
    change_items = change_set.get("items")
    if not isinstance(change_items, list):
        _raise_integrity(
            "plan.invalid_schema", "changeSet.items must be an array", path="/changeSet/items"
        )

    counts = {
        "create": 0,
        "replace": 0,
        "no-op": 0,
        "remote-only": 0,
        "blocked": 0,
    }
    previous_item_sort: tuple[int, str] | None = None
    for index, item in enumerate(change_items):
        item_path = f"/changeSet/items/{index}"
        if not isinstance(item, dict):
            _raise_integrity(
                "plan.invalid_schema", "changeSet item must be an object", path=item_path
            )
        resource_type = item.get("type")
        if resource_type not in {"businessDomain", "dataProduct", "glossaryTerm"}:
            _raise_integrity(
                "plan.invalid_schema",
                "changeSet item type must be businessDomain, dataProduct, or glossaryTerm",
                path=f"{item_path}/type",
            )
        item_id = item.get("id")
        if normalize_uuid_string(item_id) is None:
            _raise_integrity(
                "plan.noncanonical_input",
                "changeSet item id must be a valid UUID",
                path=f"{item_path}/id",
            )
        type_rank = {"businessDomain": 0, "dataProduct": 1, "glossaryTerm": 2}[str(resource_type)]
        item_sort = (type_rank, str(item_id))
        if previous_item_sort is not None and item_sort < previous_item_sort:
            _raise_integrity(
                "plan.noncanonical_input",
                "changeSet items must be sorted by type then id",
                path=item_path,
            )
        previous_item_sort = item_sort

        outcome = item.get("outcome")
        if outcome not in counts:
            _raise_integrity("plan.invalid_schema", "invalid changeSet outcome", path=item_path)
        counts[outcome] += 1

        reasons = item.get("reasons")
        if not isinstance(reasons, list):
            _raise_integrity(
                "plan.invalid_schema", "reasons must be an array", path=f"{item_path}/reasons"
            )
        reason_keys: set[tuple[str, str, str | None, str | None]] = set()
        previous_reason_sort: tuple[str, str] | None = None
        for r_index, reason_item in enumerate(reasons):
            if not isinstance(reason_item, dict):
                _raise_integrity(
                    "plan.invalid_schema",
                    "reason must be an object",
                    path=f"{item_path}/reasons/{r_index}",
                )
            r_path = f"{item_path}/reasons/{r_index}"
            _validate_reason_shape_v3(reason_item, path=r_path)
            key = (
                str(reason_item.get("path")),
                str(reason_item.get("code")),
                reason_item.get("before"),
                reason_item.get("after"),
            )
            if key in reason_keys:
                _raise_integrity("plan.invalid_reason", "duplicate reason", path=r_path)
            reason_keys.add(key)
            sort_key = (str(reason_item.get("path")), str(reason_item.get("code")))
            if previous_reason_sort is not None and sort_key < previous_reason_sort:
                _raise_integrity(
                    "plan.noncanonical_input",
                    "reasons must be ordered by path then code",
                    path=r_path,
                )
            previous_reason_sort = sort_key

        _validate_outcome_reasons_v3(
            resource_type=str(resource_type),
            outcome=str(outcome),
            reasons=reasons,
            has_desired=(str(resource_type), str(item_id)) in desired_lookup,
            desired=desired_lookup.get((str(resource_type), str(item_id))),
            path=item_path,
        )

    operations = document.get("operations")
    if not isinstance(operations, list):
        _raise_integrity("plan.invalid_schema", "operations must be an array", path="/operations")

    expected_ops: list[tuple[str, str, str]] = []
    bd_items = [item for item in change_items if item.get("type") == "businessDomain"]
    dp_items = [item for item in change_items if item.get("type") == "dataProduct"]
    gt_items = [item for item in change_items if item.get("type") == "glossaryTerm"]
    create_ids = [item["id"] for item in bd_items if item["outcome"] == "create"]
    parent_by_id: dict[str, str | None] = {}
    for domain_id, raw in desired_lookup.items():
        if domain_id[0] != "businessDomain":
            continue
        parent_by_id[domain_id[1]] = raw["properties"].get("parentId")
    ordered_creates = _topological_create_ids(create_ids, parent_by_id)
    for domain_id in ordered_creates:
        expected_ops.append(("businessDomain", "create", domain_id))
    replace_ids = sorted(
        item["id"]
        for item in bd_items
        if item["outcome"] == "replace"
        and "remote.unsupported_configurable_field" not in _reason_codes(item["reasons"])
    )
    for domain_id in replace_ids:
        expected_ops.append(("businessDomain", "replace", domain_id))
    dp_create_ids = sorted(item["id"] for item in dp_items if item["outcome"] == "create")
    for product_id in dp_create_ids:
        expected_ops.append(("dataProduct", "create", product_id))
    dp_replace_ids = sorted(
        item["id"]
        for item in dp_items
        if item["outcome"] == "replace"
        and "remote.unsupported_configurable_field" not in _reason_codes(item["reasons"])
        and "remote.status_blocks_replace" not in _reason_codes(item["reasons"])
        and "plan.domain_move_unverified" not in _reason_codes(item["reasons"])
    )
    for product_id in dp_replace_ids:
        expected_ops.append(("dataProduct", "replace", product_id))
    parent_by_gt: dict[str, str | None] = {}
    for term_key, raw in desired_lookup.items():
        if term_key[0] != "glossaryTerm":
            continue
        parent_by_gt[term_key[1]] = raw["properties"].get("parentId")
    gt_create_ids = [item["id"] for item in gt_items if item["outcome"] == "create"]
    ordered_gt_creates = _topological_create_ids(gt_create_ids, parent_by_gt)
    for term_id in ordered_gt_creates:
        expected_ops.append(("glossaryTerm", "create", term_id))
    gt_replace_ids = sorted(
        item["id"]
        for item in gt_items
        if item["outcome"] == "replace"
        and "remote.unsupported_configurable_field" not in _reason_codes(item["reasons"])
        and "remote.status_blocks_replace" not in _reason_codes(item["reasons"])
        and "plan.glossary_term_domain_move_unverified" not in _reason_codes(item["reasons"])
    )
    for term_id in gt_replace_ids:
        expected_ops.append(("glossaryTerm", "replace", term_id))

    if len(operations) != len(expected_ops):
        _raise_integrity(
            "plan.invalid_operation_mapping",
            "operations must match eligible create/replace changeSet items",
            path="/operations",
        )

    previous_op_sort: tuple[int, int, str] | None = None
    for index, operation in enumerate(operations):
        op_path = f"/operations/{index}"
        if operation.get("sequence") != index + 1:
            _raise_integrity(
                "plan.invalid_operation_mapping",
                "operation sequence must be contiguous from 1",
                path=op_path,
            )
        action = operation.get("action")
        op_type = operation.get("type")
        op_id = operation.get("id")
        if action not in {"create", "replace"}:
            _raise_integrity(
                "plan.invalid_operation_mapping",
                "operation action must be create or replace",
                path=op_path,
            )
        if op_type not in {"businessDomain", "dataProduct", "glossaryTerm"}:
            _raise_integrity(
                "plan.invalid_operation_mapping",
                "operation type must be businessDomain, dataProduct, or glossaryTerm",
                path=op_path,
            )
        if normalize_uuid_string(op_id) is None:
            _raise_integrity(
                "plan.noncanonical_input",
                "operation id must be a valid UUID",
                path=f"{op_path}/id",
            )
        type_order = {"businessDomain": 0, "dataProduct": 1, "glossaryTerm": 2}[str(op_type)]
        action_order = 0 if action == "create" else 1
        op_sort = (type_order, action_order, str(op_id))
        if previous_op_sort is not None and op_sort < previous_op_sort:
            _raise_integrity(
                "plan.noncanonical_input",
                "operations must be ordered by resource type, action, then id",
                path=op_path,
            )
        previous_op_sort = op_sort
        expected_type, expected_action, expected_id = expected_ops[index]
        if action != expected_action or str(op_id) != expected_id or op_type != expected_type:
            _raise_integrity(
                "plan.invalid_operation_mapping",
                "operation does not match changeSet create/replace mapping",
                path=op_path,
            )

    summary = document.get("summary")
    expected_summary = {
        "total": len(change_items),
        "create": counts["create"],
        "replace": counts["replace"],
        "noOp": counts["no-op"],
        "remoteOnly": counts["remote-only"],
        "blocked": counts["blocked"],
        "operations": len(operations),
    }
    if summary != expected_summary:
        _raise_integrity(
            "plan.invalid_summary", "summary counts do not match changeSet", path="/summary"
        )

    expected_eligibility = "blocked" if counts["blocked"] > 0 else "ready"
    if document.get("executionEligibility") != expected_eligibility:
        _raise_integrity(
            "plan.invalid_eligibility",
            "executionEligibility does not match blocked count",
            path="/executionEligibility",
        )

    without_identity = {key: value for key, value in document.items() if key != "planIdentity"}
    expected_plan_identity = compute_plan_identity(without_identity)
    if document.get("planIdentity") != expected_plan_identity:
        _raise_integrity(
            "plan.identity_mismatch",
            "planIdentity mismatch",
            path="/planIdentity",
        )


def validate_plan_document_schema_v3(document: dict[str, Any]) -> None:
    schema_failed = False
    try:
        schema = load_plan_v3_schema()
        Draft202012Validator(schema).validate(document)
    except Exception:
        schema_failed = True
    if schema_failed:
        raise PlanSchemaError("plan.invalid_schema", "plan document failed schema validation")


def validate_plan_document_for_serialization_v3(document: dict[str, Any]) -> None:
    """Schema + semantic validation for the official v3 serializer boundary."""
    validate_plan_document_schema_v3(document)
    validate_plan_document_semantics_v3(document)


def dumps_plan_canonical_v3(document: dict[str, Any]) -> str:
    validate_plan_document_for_serialization_v3(document)
    return dumps_canonical(document)
