"""Normalize Unified Catalog Glossary Term enumerate items (remote-state/v3)."""

from __future__ import annotations

from typing import Any

from purview_governance.config.diagnostics import classify_unknown_field, json_pointer
from purview_governance.remote_state.api_datetime import validate_api_datetime_string
from purview_governance.remote_state.canonical import compute_value_identity
from purview_governance.remote_state.errors import RemoteStateError
from purview_governance.remote_state.glossary_term_policy import (
    CONTACT_ENTRY_KNOWN,
    DEFERRED_CONFIGURABLE_FIELDS,
    GLOSSARY_TERM_STATUSES,
    GLOSSARY_TERM_TOP_LEVEL_KNOWN,
    MANAGED_ATTRIBUTE_KNOWN,
    PROVISIONING_STATES,
    REASON_DUPLICATE_ACRONYM,
    REASON_DUPLICATE_OWNER_ID,
    REASON_INVALID_ACRONYMS,
    REASON_INVALID_PARENT_ID,
    REASON_PROVISIONING_BLOCKED,
    SYSTEM_DATA_KNOWN,
    TERM_RESOURCE_KNOWN,
)
from purview_governance.remote_state.models import UnsupportedConfigurableField
from purview_governance.remote_state.models_v3 import (
    NormalizedGlossaryTerm,
    UninterpretedGlossaryTerm,
)
from purview_governance.uuid_utils import normalize_uuid_string

_DESCRIPTION_MAX_LENGTH = 10_000


def _raise(code: str, message: str, *path_parts: object) -> None:
    path = json_pointer(*path_parts) if path_parts else ""
    raise RemoteStateError(code, message, path=path)


def _require_object(value: object, *, path_parts: tuple[object, ...]) -> dict[str, Any]:
    if not isinstance(value, dict):
        _raise("remote_state.invalid_shape", "expected a JSON object", *path_parts)
    return value


def _reject_unknown_key(
    key: str,
    known: frozenset[str],
    *,
    path_parts: tuple[object, ...],
) -> None:
    if key in known:
        return
    if classify_unknown_field(key) == "config.secret_field_forbidden":
        _raise(
            "remote_state.sensitive_field",
            f"sensitive field {key!r} is not allowed in remote state",
            *(*path_parts, key),
        )
    _raise(
        "remote_state.unknown_field",
        f"unknown field {key!r} is not allowed",
        *(*path_parts, key),
    )


def _check_unknown_keys(
    obj: dict[str, Any],
    known: frozenset[str],
    *,
    path_parts: tuple[object, ...],
) -> None:
    for key in obj:
        _reject_unknown_key(key, known, path_parts=path_parts)


def _require_non_empty_string(value: object, *, path_parts: tuple[object, ...]) -> str:
    if not isinstance(value, str) or not value.strip():
        _raise("remote_state.invalid_shape", "expected a non-empty string", *path_parts)
    return value.strip()


def _canonicalize_json_value(value: object) -> object:
    if isinstance(value, dict):
        return {key: _canonicalize_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_canonicalize_json_value(item) for item in value]
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, str):
        return value
    if value is None:
        return None
    _raise("remote_state.invalid_shape", "unsupported JSON value type")
    raise AssertionError("unreachable")


def _extract_provisioning_state(raw: dict[str, Any]) -> str | None:
    if "systemData" not in raw:
        return None
    system_data = _require_object(raw["systemData"], path_parts=("systemData",))
    _check_unknown_keys(system_data, SYSTEM_DATA_KNOWN, path_parts=("systemData",))
    for field in ("createdAt", "lastModifiedAt", "expiredAt"):
        if field in system_data:
            try:
                validate_api_datetime_string(system_data[field])
            except ValueError as exc:
                _raise("remote_state.invalid_shape", str(exc), "systemData", field)
    for field in ("createdBy", "lastModifiedBy", "expiredBy"):
        if field in system_data and normalize_uuid_string(system_data[field]) is None:
            _raise(
                "remote_state.invalid_shape",
                "systemData actor must be a valid UUID",
                "systemData",
                field,
            )
    if "provisioningState" not in system_data:
        return None
    provisioning_state = system_data["provisioningState"]
    if not isinstance(provisioning_state, str) or provisioning_state not in PROVISIONING_STATES:
        _raise(
            "remote_state.invalid_shape",
            "systemData.provisioningState is not a documented enum value",
            "systemData",
            "provisioningState",
        )
    return provisioning_state


def _normalize_managed_attribute(
    value: object, *, path_parts: tuple[object, ...]
) -> dict[str, Any]:
    obj = _require_object(value, path_parts=path_parts)
    _check_unknown_keys(obj, MANAGED_ATTRIBUTE_KNOWN, path_parts=path_parts)
    normalized: dict[str, Any] = {
        "name": _require_non_empty_string(obj["name"], path_parts=(*path_parts, "name")),
    }
    if "value" in obj and isinstance(obj["value"], str):
        normalized["value"] = obj["value"]
    if "isRequired" in obj and isinstance(obj["isRequired"], bool):
        normalized["isRequired"] = obj["isRequired"]
    return normalized


def _normalize_term_resource(value: object, *, path_parts: tuple[object, ...]) -> dict[str, Any]:
    obj = _require_object(value, path_parts=path_parts)
    _check_unknown_keys(obj, TERM_RESOURCE_KNOWN, path_parts=path_parts)
    normalized: dict[str, Any] = {}
    if "name" in obj and isinstance(obj["name"], str):
        normalized["name"] = obj["name"]
    if "url" in obj:
        normalized["url"] = _require_non_empty_string(obj["url"], path_parts=(*path_parts, "url"))
    return normalized


def _normalize_contact_entry(value: object, *, path_parts: tuple[object, ...]) -> dict[str, Any]:
    obj = _require_object(value, path_parts=path_parts)
    _check_unknown_keys(obj, CONTACT_ENTRY_KNOWN, path_parts=path_parts)
    contact_id = normalize_uuid_string(obj.get("id"))
    if contact_id is None:
        _raise(
            "remote_state.invalid_shape", "contact id must be a valid UUID", *(*path_parts, "id")
        )
    normalized: dict[str, Any] = {"id": contact_id}
    if "description" in obj and isinstance(obj["description"], str):
        normalized["description"] = obj["description"]
    return normalized


def _normalize_deferred_field(field_name: str, value: object) -> object:
    if field_name == "managedAttributes":
        items = value if isinstance(value, list) else None
        if items is None:
            _raise("remote_state.invalid_shape", "managedAttributes must be an array", field_name)
        return [
            _normalize_managed_attribute(item, path_parts=("managedAttributes", index))
            for index, item in enumerate(items)
        ]
    if field_name == "resources":
        items = value if isinstance(value, list) else None
        if items is None:
            _raise("remote_state.invalid_shape", "resources must be an array", field_name)
        return [
            _normalize_term_resource(item, path_parts=("resources", index))
            for index, item in enumerate(items)
        ]
    raise AssertionError(f"unsupported deferred field {field_name!r}")


def _record_deferred_field(
    raw: dict[str, Any],
    field_name: str,
    unsupported: list[UnsupportedConfigurableField],
) -> None:
    if field_name not in raw:
        return
    value = raw[field_name]
    if field_name == "resources" and isinstance(value, list) and not value:
        return
    normalized = _canonicalize_json_value(_normalize_deferred_field(field_name, value))
    unsupported.append(
        UnsupportedConfigurableField(
            path=json_pointer(field_name),
            value_identity=compute_value_identity(normalized),
        )
    )


def _record_deferred_contact_role(
    raw: dict[str, Any],
    role: str,
    unsupported: list[UnsupportedConfigurableField],
) -> None:
    contacts = raw.get("contacts")
    if not isinstance(contacts, dict) or role not in contacts:
        return
    entries = contacts[role]
    if not isinstance(entries, list):
        _raise("remote_state.invalid_shape", f"contacts.{role} must be an array", "contacts", role)
    normalized = _canonicalize_json_value(
        [
            _normalize_contact_entry(item, path_parts=("contacts", role, index))
            for index, item in enumerate(entries)
        ]
    )
    unsupported.append(
        UnsupportedConfigurableField(
            path=json_pointer("contacts", role),
            value_identity=compute_value_identity(normalized),
        )
    )


def _normalize_owners(
    raw: dict[str, Any],
    *,
    term_id: str,
) -> list[dict[str, Any]] | UninterpretedGlossaryTerm:
    contacts = raw.get("contacts")
    if not isinstance(contacts, dict) or "owner" not in contacts:
        return []
    owners_raw = contacts["owner"]
    if not isinstance(owners_raw, list):
        _raise("remote_state.invalid_shape", "contacts.owner must be an array", "contacts", "owner")
    owners = [
        _normalize_contact_entry(item, path_parts=("contacts", "owner", index))
        for index, item in enumerate(owners_raw)
    ]
    seen: set[str] = set()
    for owner in owners:
        if owner["id"] in seen:
            return UninterpretedGlossaryTerm(id=term_id, reason_code=REASON_DUPLICATE_OWNER_ID)
        seen.add(owner["id"])
    return sorted(owners, key=lambda item: item["id"])


def _normalize_parent_id(
    raw: dict[str, Any],
    *,
    term_id: str,
) -> str | None | UninterpretedGlossaryTerm:
    if "parentId" not in raw:
        return None
    parent_raw = raw["parentId"]
    if parent_raw is None:
        return UninterpretedGlossaryTerm(id=term_id, reason_code=REASON_INVALID_PARENT_ID)
    parent_id = normalize_uuid_string(parent_raw)
    if parent_id is None:
        return UninterpretedGlossaryTerm(id=term_id, reason_code=REASON_INVALID_PARENT_ID)
    return parent_id


def _normalize_acronyms(
    raw: dict[str, Any],
    *,
    term_id: str,
) -> list[str] | UninterpretedGlossaryTerm | None:
    if "acronyms" not in raw:
        return None
    acronyms_raw = raw["acronyms"]
    if acronyms_raw is None:
        return UninterpretedGlossaryTerm(id=term_id, reason_code=REASON_INVALID_ACRONYMS)
    if not isinstance(acronyms_raw, list):
        _raise("remote_state.invalid_shape", "acronyms must be an array", "acronyms")
    if not acronyms_raw:
        return []
    seen: set[str] = set()
    normalized: list[str] = []
    for entry in acronyms_raw:
        if not isinstance(entry, str) or not entry:
            return UninterpretedGlossaryTerm(id=term_id, reason_code=REASON_INVALID_ACRONYMS)
        if entry in seen:
            return UninterpretedGlossaryTerm(id=term_id, reason_code=REASON_DUPLICATE_ACRONYM)
        seen.add(entry)
        normalized.append(entry)
    return sorted(normalized)


def normalize_glossary_term(
    raw: dict[str, Any],
) -> NormalizedGlossaryTerm | UninterpretedGlossaryTerm:
    """Normalize one Glossary Term enumerate item."""
    _check_unknown_keys(raw, GLOSSARY_TERM_TOP_LEVEL_KNOWN, path_parts=())

    term_id = normalize_uuid_string(raw.get("id"))
    if term_id is None:
        _raise("remote_state.invalid_shape", "Glossary Term id must be a valid UUID", "id")

    provisioning_state = _extract_provisioning_state(raw)
    if provisioning_state in {"SoftDeleted", "Unknown"}:
        return UninterpretedGlossaryTerm(id=term_id, reason_code=REASON_PROVISIONING_BLOCKED)

    name = _require_non_empty_string(raw.get("name"), path_parts=("name",))
    domain_id = normalize_uuid_string(raw.get("domain"))
    if domain_id is None:
        _raise("remote_state.invalid_shape", "Glossary Term domain must be a valid UUID", "domain")

    description = _require_non_empty_string(raw.get("description"), path_parts=("description",))
    if len(description) > _DESCRIPTION_MAX_LENGTH:
        _raise(
            "remote_state.invalid_shape",
            f"description must not exceed {_DESCRIPTION_MAX_LENGTH} characters",
            "description",
        )

    status = raw.get("status")
    if not isinstance(status, str) or status not in GLOSSARY_TERM_STATUSES:
        _raise(
            "remote_state.invalid_shape",
            "Glossary Term status is not a documented enum value",
            "status",
        )

    owners_result = _normalize_owners(raw, term_id=term_id)
    if isinstance(owners_result, UninterpretedGlossaryTerm):
        return owners_result

    parent_result = _normalize_parent_id(raw, term_id=term_id)
    if isinstance(parent_result, UninterpretedGlossaryTerm):
        return parent_result

    acronyms_result = _normalize_acronyms(raw, term_id=term_id)
    if isinstance(acronyms_result, UninterpretedGlossaryTerm):
        return acronyms_result

    properties: dict[str, Any] = {
        "name": name,
        "domain": domain_id,
        "description": description,
    }
    if owners_result:
        properties["owners"] = owners_result
    if parent_result is not None:
        properties["parentId"] = parent_result
    if acronyms_result is not None:
        properties["acronyms"] = acronyms_result

    safety_properties: dict[str, Any] = {"status": status}
    if provisioning_state is not None:
        safety_properties["provisioningState"] = provisioning_state

    unsupported: list[UnsupportedConfigurableField] = []
    for field_name in sorted(DEFERRED_CONFIGURABLE_FIELDS):
        _record_deferred_field(raw, field_name, unsupported)
    for role in ("expert", "databaseAdmin"):
        _record_deferred_contact_role(raw, role, unsupported)

    return NormalizedGlossaryTerm(
        id=term_id,
        properties=properties,
        safety_properties=safety_properties,
        unsupported_configurable_fields=tuple(unsupported),
    )
