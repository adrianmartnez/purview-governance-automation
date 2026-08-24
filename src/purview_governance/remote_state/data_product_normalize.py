"""Normalize Unified Catalog Data Product enumerate items (remote-state/v3)."""

from __future__ import annotations

from typing import Any

from purview_governance.config.diagnostics import classify_unknown_field, json_pointer
from purview_governance.remote_state.api_datetime import validate_api_datetime_string
from purview_governance.remote_state.canonical import compute_value_identity
from purview_governance.remote_state.data_product_policy import (
    ADDITIONAL_PROPERTIES_KNOWN,
    AUDIENCE_VALUES,
    CONTACT_ENTRY_KNOWN,
    DATA_PRODUCT_COMPARABLE_PROPERTIES,
    DATA_PRODUCT_STATUSES,
    DATA_PRODUCT_TOP_LEVEL_KNOWN,
    DATA_PRODUCT_TYPES,
    DEFERRED_CONFIGURABLE_FIELDS,
    EXTERNAL_LINK_KNOWN,
    MANAGED_ATTRIBUTE_KNOWN,
    PROVISIONING_STATES,
    REASON_DUPLICATE_AUDIENCE,
    REASON_DUPLICATE_OWNER_ID,
    REASON_PROVISIONING_BLOCKED,
    REASON_UNSUPPORTED_TYPE,
    SYSTEM_DATA_KNOWN,
    UPDATE_FREQUENCY_VALUES,
)
from purview_governance.remote_state.errors import RemoteStateError
from purview_governance.remote_state.models import UnsupportedConfigurableField
from purview_governance.remote_state.models_v3 import (
    NormalizedDataProduct,
    UninterpretedDataProduct,
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


def _normalize_external_link(value: object, *, path_parts: tuple[object, ...]) -> dict[str, Any]:
    obj = _require_object(value, path_parts=path_parts)
    _check_unknown_keys(obj, EXTERNAL_LINK_KNOWN, path_parts=path_parts)
    normalized: dict[str, Any] = {}
    if "url" in obj:
        normalized["url"] = _require_non_empty_string(obj["url"], path_parts=(*path_parts, "url"))
    if "name" in obj and isinstance(obj["name"], str):
        normalized["name"] = obj["name"]
    if "dataAssetId" in obj:
        asset_id = normalize_uuid_string(obj["dataAssetId"])
        if asset_id is None:
            _raise(
                "remote_state.invalid_shape",
                "external link dataAssetId must be a valid UUID",
                *(*path_parts, "dataAssetId"),
            )
        normalized["dataAssetId"] = asset_id
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
    if field_name in {"termsOfUse", "documentation"}:
        items = value if isinstance(value, list) else None
        if items is None:
            _raise("remote_state.invalid_shape", f"{field_name} must be an array", field_name)
        return [
            _normalize_external_link(item, path_parts=(field_name, index))
            for index, item in enumerate(items)
        ]
    if field_name == "sensitivityLabel":
        if isinstance(value, str):
            return value
        _raise("remote_state.invalid_shape", "sensitivityLabel must be a string", field_name)
    raise AssertionError(f"unsupported deferred field {field_name!r}")


def _record_deferred_field(
    raw: dict[str, Any],
    field_name: str,
    unsupported: list[UnsupportedConfigurableField],
) -> None:
    if field_name not in raw:
        return
    normalized = _canonicalize_json_value(_normalize_deferred_field(field_name, raw[field_name]))
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
    product_id: str,
) -> list[dict[str, Any]] | UninterpretedDataProduct:
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
            return UninterpretedDataProduct(id=product_id, reason_code=REASON_DUPLICATE_OWNER_ID)
        seen.add(owner["id"])
    return sorted(owners, key=lambda item: item["id"])


def _normalize_audience(
    raw: dict[str, Any],
    *,
    product_id: str,
) -> list[str] | UninterpretedDataProduct | None:
    if "audience" not in raw:
        return None
    audience = raw["audience"]
    if not isinstance(audience, list):
        _raise("remote_state.invalid_shape", "audience must be an array", "audience")
    normalized: list[str] = []
    seen: set[str] = set()
    for index, entry in enumerate(audience):
        if not isinstance(entry, str) or entry not in AUDIENCE_VALUES:
            _raise(
                "remote_state.invalid_shape",
                "audience entry is not a documented enum value",
                "audience",
                index,
            )
        if entry in seen:
            return UninterpretedDataProduct(id=product_id, reason_code=REASON_DUPLICATE_AUDIENCE)
        seen.add(entry)
        normalized.append(entry)
    return sorted(normalized)


def normalize_data_product(
    raw: dict[str, Any],
) -> NormalizedDataProduct | UninterpretedDataProduct:
    """Normalize one Data Product enumerate item."""
    _check_unknown_keys(raw, DATA_PRODUCT_TOP_LEVEL_KNOWN, path_parts=())
    if "additionalProperties" in raw:
        additional = _require_object(
            raw["additionalProperties"], path_parts=("additionalProperties",)
        )
        _check_unknown_keys(
            additional, ADDITIONAL_PROPERTIES_KNOWN, path_parts=("additionalProperties",)
        )

    product_id = normalize_uuid_string(raw.get("id"))
    if product_id is None:
        _raise("remote_state.invalid_shape", "Data Product id must be a valid UUID", "id")

    provisioning_state = _extract_provisioning_state(raw)
    if provisioning_state in {"SoftDeleted", "Unknown"}:
        return UninterpretedDataProduct(id=product_id, reason_code=REASON_PROVISIONING_BLOCKED)

    name = _require_non_empty_string(raw.get("name"), path_parts=("name",))
    domain_id = normalize_uuid_string(raw.get("domain"))
    if domain_id is None:
        _raise("remote_state.invalid_shape", "Data Product domain must be a valid UUID", "domain")

    product_type = raw.get("type")
    if not isinstance(product_type, str) or product_type not in DATA_PRODUCT_TYPES:
        return UninterpretedDataProduct(id=product_id, reason_code=REASON_UNSUPPORTED_TYPE)

    description = _require_non_empty_string(raw.get("description"), path_parts=("description",))
    if len(description) > _DESCRIPTION_MAX_LENGTH:
        _raise(
            "remote_state.invalid_shape",
            f"description must not exceed {_DESCRIPTION_MAX_LENGTH} characters",
            "description",
        )
    business_use = _require_non_empty_string(raw.get("businessUse"), path_parts=("businessUse",))

    status = raw.get("status")
    if not isinstance(status, str) or status not in DATA_PRODUCT_STATUSES:
        _raise(
            "remote_state.invalid_shape",
            "Data Product status is not a documented enum value",
            "status",
        )

    owners_result = _normalize_owners(raw, product_id=product_id)
    if isinstance(owners_result, UninterpretedDataProduct):
        return owners_result

    audience_result = _normalize_audience(raw, product_id=product_id)
    if isinstance(audience_result, UninterpretedDataProduct):
        return audience_result

    properties: dict[str, Any] = {
        "name": name,
        "domain": domain_id,
        "type": product_type,
        "description": description,
        "businessUse": business_use,
    }
    if owners_result:
        properties["owners"] = owners_result
    if audience_result is not None:
        properties["audience"] = audience_result

    if "updateFrequency" in raw:
        freq = raw["updateFrequency"]
        if not isinstance(freq, str) or freq not in UPDATE_FREQUENCY_VALUES:
            _raise(
                "remote_state.invalid_shape",
                "updateFrequency is not a documented enum value",
                "updateFrequency",
            )
        properties["updateFrequency"] = freq

    if "endorsed" in raw:
        endorsed = raw["endorsed"]
        if not isinstance(endorsed, bool):
            _raise("remote_state.invalid_shape", "endorsed must be a boolean", "endorsed")
        properties["endorsed"] = endorsed

    unexpected = set(properties) - DATA_PRODUCT_COMPARABLE_PROPERTIES
    if unexpected:
        raise AssertionError(f"unexpected comparable properties: {sorted(unexpected)!r}")

    safety_properties: dict[str, Any] = {"status": status}
    if provisioning_state is not None:
        safety_properties["provisioningState"] = provisioning_state

    unsupported: list[UnsupportedConfigurableField] = []
    for field_name in sorted(DEFERRED_CONFIGURABLE_FIELDS):
        _record_deferred_field(raw, field_name, unsupported)
    for role in ("expert", "databaseAdmin"):
        _record_deferred_contact_role(raw, role, unsupported)

    return NormalizedDataProduct(
        id=product_id,
        properties=properties,
        safety_properties=safety_properties,
        unsupported_configurable_fields=tuple(unsupported),
    )
