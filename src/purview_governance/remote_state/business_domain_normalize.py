"""Normalize Unified Catalog Business Domain enumerate items (remote-state/v3)."""

from __future__ import annotations

from typing import Any

from purview_governance.config.diagnostics import classify_unknown_field, json_pointer
from purview_governance.remote_state.business_domain_policy import (
    BUSINESS_DOMAIN_COMPARABLE_PROPERTIES,
    BUSINESS_DOMAIN_STATUSES,
    BUSINESS_DOMAIN_TOP_LEVEL_KNOWN,
    BUSINESS_DOMAIN_TYPES,
    DEFERRED_CONFIGURABLE_FIELDS,
    MANAGED_ATTRIBUTE_KNOWN,
    PARENT_COLLECTION_KNOWN,
    PARENT_COLLECTION_TYPES,
    PLATFORM_DOMAIN_KNOWN,
    REASON_HIERARCHY_AMBIGUOUS,
    RELATED_COLLECTION_KNOWN,
    THUMBNAIL_KNOWN,
)
from purview_governance.remote_state.canonical import compute_value_identity
from purview_governance.remote_state.errors import RemoteStateError
from purview_governance.remote_state.models import UnsupportedConfigurableField
from purview_governance.remote_state.models_v3 import (
    NormalizedBusinessDomain,
    UninterpretedBusinessDomain,
)
from purview_governance.uuid_utils import normalize_uuid_string


def _raise(code: str, message: str, *path_parts: object) -> None:
    path = json_pointer(*path_parts) if path_parts else ""
    raise RemoteStateError(code, message, path=path)


def _require_object(value: object, *, path_parts: tuple[object, ...]) -> dict[str, Any]:
    if not isinstance(value, dict):
        _raise(
            "remote_state.invalid_shape",
            "expected a JSON object",
            *path_parts,
        )
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
        _raise(
            "remote_state.invalid_shape",
            "expected a non-empty string",
            *path_parts,
        )
    return value.strip()


def _canonicalize_json_value(value: object) -> object:
    """Recursively normalize JSON values, preserving array order."""
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
    _raise(
        "remote_state.invalid_shape",
        "unsupported JSON value type in deferred configurable field",
    )
    raise AssertionError("unreachable")


def _normalize_parent_collection(
    value: object,
    *,
    path_parts: tuple[object, ...],
) -> dict[str, Any]:
    obj = _require_object(value, path_parts=path_parts)
    _check_unknown_keys(obj, PARENT_COLLECTION_KNOWN, path_parts=path_parts)
    if "refName" not in obj:
        _raise(
            "remote_state.invalid_shape",
            "parentCollection.refName is required",
            *(*path_parts, "refName"),
        )
    ref_name = _require_non_empty_string(
        obj["refName"],
        path_parts=(*path_parts, "refName"),
    )
    if "type" not in obj:
        _raise(
            "remote_state.invalid_shape",
            "parentCollection.type is required",
            *(*path_parts, "type"),
        )
    coll_type = obj["type"]
    if not isinstance(coll_type, str) or coll_type not in PARENT_COLLECTION_TYPES:
        _raise(
            "remote_state.invalid_shape",
            "parentCollection.type must be CollectionReference",
            *(*path_parts, "type"),
        )
    return {"refName": ref_name, "type": coll_type}


def _normalize_related_collection(
    value: object,
    *,
    path_parts: tuple[object, ...],
) -> dict[str, Any]:
    obj = _require_object(value, path_parts=path_parts)
    _check_unknown_keys(obj, RELATED_COLLECTION_KNOWN, path_parts=path_parts)
    if "name" not in obj:
        _raise(
            "remote_state.invalid_shape",
            "relatedCollections.name is required",
            *(*path_parts, "name"),
        )
    normalized: dict[str, Any] = {
        "name": _require_non_empty_string(obj["name"], path_parts=(*path_parts, "name")),
    }
    if "friendlyName" in obj:
        friendly = obj["friendlyName"]
        if friendly is None:
            _raise(
                "remote_state.invalid_shape",
                "relatedCollections.friendlyName must not be null",
                *(*path_parts, "friendlyName"),
            )
        if not isinstance(friendly, str):
            _raise(
                "remote_state.invalid_shape",
                "relatedCollections.friendlyName must be a string",
                *(*path_parts, "friendlyName"),
            )
        normalized["friendlyName"] = friendly
    if "parentCollection" in obj:
        parent = obj["parentCollection"]
        if parent is None:
            _raise(
                "remote_state.invalid_shape",
                "relatedCollections.parentCollection must not be null",
                *(*path_parts, "parentCollection"),
            )
        normalized["parentCollection"] = _normalize_parent_collection(
            parent,
            path_parts=(*path_parts, "parentCollection"),
        )
    return normalized


def _normalize_platform_domain(
    value: object,
    *,
    path_parts: tuple[object, ...],
) -> dict[str, Any]:
    obj = _require_object(value, path_parts=path_parts)
    _check_unknown_keys(obj, PLATFORM_DOMAIN_KNOWN, path_parts=path_parts)
    if "name" not in obj:
        _raise(
            "remote_state.invalid_shape",
            "domains.name is required",
            *(*path_parts, "name"),
        )
    normalized: dict[str, Any] = {
        "name": _require_non_empty_string(obj["name"], path_parts=(*path_parts, "name")),
    }
    if "friendlyName" in obj:
        friendly = obj["friendlyName"]
        if friendly is None:
            _raise(
                "remote_state.invalid_shape",
                "domains.friendlyName must not be null",
                *(*path_parts, "friendlyName"),
            )
        if not isinstance(friendly, str):
            _raise(
                "remote_state.invalid_shape",
                "domains.friendlyName must be a string",
                *(*path_parts, "friendlyName"),
            )
        normalized["friendlyName"] = friendly
    if "relatedCollections" in obj:
        related = obj["relatedCollections"]
        if related is None:
            _raise(
                "remote_state.invalid_shape",
                "domains.relatedCollections must not be null",
                *(*path_parts, "relatedCollections"),
            )
        if not isinstance(related, list):
            _raise(
                "remote_state.invalid_shape",
                "domains.relatedCollections must be an array",
                *(*path_parts, "relatedCollections"),
            )
        normalized["relatedCollections"] = [
            _normalize_related_collection(
                item,
                path_parts=(*path_parts, "relatedCollections", index),
            )
            for index, item in enumerate(related)
        ]
    return normalized


def _normalize_managed_attribute(
    value: object,
    *,
    path_parts: tuple[object, ...],
) -> dict[str, Any]:
    obj = _require_object(value, path_parts=path_parts)
    _check_unknown_keys(obj, MANAGED_ATTRIBUTE_KNOWN, path_parts=path_parts)
    if "name" not in obj:
        _raise(
            "remote_state.invalid_shape",
            "managedAttributes.name is required",
            *(*path_parts, "name"),
        )
    normalized: dict[str, Any] = {
        "name": _require_non_empty_string(obj["name"], path_parts=(*path_parts, "name")),
    }
    if "value" in obj:
        attr_value = obj["value"]
        if attr_value is None:
            _raise(
                "remote_state.invalid_shape",
                "managedAttributes.value must not be null",
                *(*path_parts, "value"),
            )
        if not isinstance(attr_value, str):
            _raise(
                "remote_state.invalid_shape",
                "managedAttributes.value must be a string",
                *(*path_parts, "value"),
            )
        normalized["value"] = attr_value
    if "isRequired" in obj:
        is_required = obj["isRequired"]
        if is_required is None:
            _raise(
                "remote_state.invalid_shape",
                "managedAttributes.isRequired must not be null",
                *(*path_parts, "isRequired"),
            )
        if not isinstance(is_required, bool):
            _raise(
                "remote_state.invalid_shape",
                "managedAttributes.isRequired must be a boolean",
                *(*path_parts, "isRequired"),
            )
        normalized["isRequired"] = is_required
    return normalized


def _normalize_thumbnail(
    value: object,
    *,
    path_parts: tuple[object, ...],
) -> dict[str, Any]:
    obj = _require_object(value, path_parts=path_parts)
    _check_unknown_keys(obj, THUMBNAIL_KNOWN, path_parts=path_parts)
    normalized: dict[str, Any] = {}
    if "color" in obj:
        color = obj["color"]
        if color is None:
            _raise(
                "remote_state.invalid_shape",
                "thumbnail.color must not be null",
                *(*path_parts, "color"),
            )
        if not isinstance(color, str):
            _raise(
                "remote_state.invalid_shape",
                "thumbnail.color must be a string",
                *(*path_parts, "color"),
            )
        normalized["color"] = color
    return normalized


def _normalize_deferred_field(
    field_name: str,
    value: object,
) -> object:
    if value is None:
        _raise(
            "remote_state.invalid_shape",
            f"{field_name} must not be null",
            field_name,
        )
    if field_name == "managedAttributes":
        if not isinstance(value, list):
            _raise(
                "remote_state.invalid_shape",
                "managedAttributes must be an array",
                "managedAttributes",
            )
        return [
            _normalize_managed_attribute(
                item,
                path_parts=("managedAttributes", index),
            )
            for index, item in enumerate(value)
        ]
    if field_name == "domains":
        if not isinstance(value, list):
            _raise(
                "remote_state.invalid_shape",
                "domains must be an array",
                "domains",
            )
        return [
            _normalize_platform_domain(item, path_parts=("domains", index))
            for index, item in enumerate(value)
        ]
    if field_name == "thumbnail":
        return _normalize_thumbnail(value, path_parts=("thumbnail",))
    msg = f"unsupported deferred field {field_name!r}"
    raise AssertionError(msg)


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


def normalize_business_domain(
    raw: dict[str, Any],
) -> NormalizedBusinessDomain | UninterpretedBusinessDomain:
    """Normalize one Business Domain enumerate item."""
    if not isinstance(raw, dict):
        _raise(
            "remote_state.invalid_shape",
            "Business Domain item must be a JSON object",
        )

    _check_unknown_keys(raw, BUSINESS_DOMAIN_TOP_LEVEL_KNOWN, path_parts=())

    if "id" not in raw:
        _raise(
            "remote_state.invalid_shape",
            "Business Domain id is required",
            "id",
        )
    domain_id = normalize_uuid_string(raw["id"])
    if domain_id is None:
        _raise(
            "remote_state.invalid_shape",
            "Business Domain id must be a valid UUID",
            "id",
        )

    if "parentId" in raw and raw["parentId"] is not None:
        parent_raw = raw["parentId"]
        parent_id = normalize_uuid_string(parent_raw)
        if parent_id is None:
            _raise(
                "remote_state.invalid_shape",
                "parentId must be a valid UUID when present",
                "parentId",
            )
        if parent_id == domain_id:
            return UninterpretedBusinessDomain(
                id=domain_id,
                reason_code=REASON_HIERARCHY_AMBIGUOUS,
            )

    if "name" not in raw:
        _raise(
            "remote_state.invalid_shape",
            "Business Domain name is required",
            "name",
        )
    name = _require_non_empty_string(raw["name"], path_parts=("name",))

    if "status" not in raw:
        _raise(
            "remote_state.invalid_shape",
            "Business Domain status is required",
            "status",
        )
    status = raw["status"]
    if not isinstance(status, str) or status not in BUSINESS_DOMAIN_STATUSES:
        _raise(
            "remote_state.invalid_shape",
            "Business Domain status is not a documented enum value",
            "status",
        )

    if "type" not in raw:
        _raise(
            "remote_state.invalid_shape",
            "Business Domain type is required",
            "type",
        )
    domain_type = raw["type"]
    if not isinstance(domain_type, str) or domain_type not in BUSINESS_DOMAIN_TYPES:
        _raise(
            "remote_state.invalid_shape",
            "Business Domain type is not a documented enum value",
            "type",
        )

    properties: dict[str, Any] = {
        "name": name,
        "status": status,
        "type": domain_type,
    }

    if "description" in raw:
        description = raw["description"]
        if description is None:
            _raise(
                "remote_state.invalid_shape",
                "description must not be null",
                "description",
            )
        if not isinstance(description, str):
            _raise(
                "remote_state.invalid_shape",
                "description must be a string",
                "description",
            )
        properties["description"] = description

    if "parentId" in raw and raw["parentId"] is not None:
        parent_id = normalize_uuid_string(raw["parentId"])
        assert parent_id is not None
        properties["parentId"] = parent_id

    if "isRestricted" in raw:
        is_restricted = raw["isRestricted"]
        if is_restricted is None:
            _raise(
                "remote_state.invalid_shape",
                "isRestricted must not be null",
                "isRestricted",
            )
        if not isinstance(is_restricted, bool):
            _raise(
                "remote_state.invalid_shape",
                "isRestricted must be a boolean",
                "isRestricted",
            )
        properties["isRestricted"] = is_restricted

    unexpected = set(properties) - BUSINESS_DOMAIN_COMPARABLE_PROPERTIES
    if unexpected:
        msg = f"unexpected comparable properties: {sorted(unexpected)!r}"
        raise AssertionError(msg)

    unsupported: list[UnsupportedConfigurableField] = []
    for field_name in sorted(DEFERRED_CONFIGURABLE_FIELDS):
        _record_deferred_field(raw, field_name, unsupported)

    return NormalizedBusinessDomain(
        id=domain_id,
        properties=properties,
        unsupported_configurable_fields=tuple(unsupported),
    )
