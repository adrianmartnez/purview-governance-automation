"""Normalize Unified Catalog Data Asset enumerate items (remote-state/v3)."""

from __future__ import annotations

from typing import Any

from purview_governance.config.diagnostics import classify_unknown_field, json_pointer
from purview_governance.remote_state.api_datetime import validate_api_datetime_string
from purview_governance.remote_state.data_asset_policy import (
    ADLS_GEN2_PATH_TYPE_PROPERTIES_KNOWN,
    AZURE_SQL_TABLE_TYPE_PROPERTIES_KNOWN,
    CONTACT_ENTRY_KNOWN,
    CONTACTS_MAP_KNOWN,
    DATA_ASSET_TOP_LEVEL_KNOWN,
    DATA_ASSET_TYPES,
    PROVISIONING_STATES,
    REASON_DUPLICATE_CLASSIFICATION,
    REASON_DUPLICATE_OWNER_ID,
    REASON_PROVISIONING_BLOCKED,
    REASON_UNKNOWN_FIELD,
    REASON_UNSUPPORTED_TYPE,
    SCHEMA_ENTRY_KNOWN,
    SOURCE_KNOWN,
    SYSTEM_DATA_KNOWN,
    TYPE_PROPERTIES_FORMAT,
)
from purview_governance.remote_state.errors import RemoteStateError
from purview_governance.remote_state.models_v3 import (
    NormalizedDataAsset,
    UninterpretedDataAsset,
)
from purview_governance.uuid_utils import normalize_uuid_string


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


def _optional_non_null_string(value: object, *, path_parts: tuple[object, ...]) -> str | None:
    if value is None:
        _raise("remote_state.invalid_shape", "explicit null is not allowed", *path_parts)
    if "description" in path_parts and value == "":
        return value
    if not isinstance(value, str):
        _raise("remote_state.invalid_shape", "expected a string", *path_parts)
    return value


def _extract_provisioning_state(raw: dict[str, Any]) -> str | None:
    if "systemData" not in raw:
        return None
    system_data = _require_object(raw["systemData"], path_parts=("systemData",))
    if system_data is None:
        _raise("remote_state.invalid_shape", "explicit null is not allowed", "systemData")
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


def _normalize_contact_entry(value: object, *, path_parts: tuple[object, ...]) -> dict[str, Any]:
    obj = _require_object(value, path_parts=path_parts)
    _check_unknown_keys(obj, CONTACT_ENTRY_KNOWN, path_parts=path_parts)
    contact_id = normalize_uuid_string(obj.get("id"))
    if contact_id is None:
        _raise(
            "remote_state.invalid_shape", "contact id must be a valid UUID", *(*path_parts, "id")
        )
    normalized: dict[str, Any] = {"id": contact_id}
    if "description" in obj:
        normalized["description"] = _require_non_empty_string(
            obj["description"], path_parts=(*path_parts, "description")
        )
    return normalized


def _normalize_contacts(
    value: object,
    *,
    asset_id: str,
) -> dict[str, list[dict[str, Any]]] | UninterpretedDataAsset:
    if value is None:
        _raise("remote_state.invalid_shape", "explicit null is not allowed", "contacts")
    obj = _require_object(value, path_parts=("contacts",))
    _check_unknown_keys(obj, CONTACTS_MAP_KNOWN, path_parts=("contacts",))
    normalized: dict[str, list[dict[str, Any]]] = {}
    for role in sorted(CONTACTS_MAP_KNOWN):
        if role not in obj:
            continue
        entries = obj[role]
        if not isinstance(entries, list):
            _raise(
                "remote_state.invalid_shape",
                f"contacts.{role} must be an array",
                "contacts",
                role,
            )
        contacts = [
            _normalize_contact_entry(item, path_parts=("contacts", role, index))
            for index, item in enumerate(entries)
        ]
        seen: set[str] = set()
        for contact in contacts:
            if contact["id"] in seen:
                return UninterpretedDataAsset(id=asset_id, reason_code=REASON_DUPLICATE_OWNER_ID)
            seen.add(contact["id"])
        normalized[role] = sorted(contacts, key=lambda item: item["id"])
    return normalized


def _normalize_classifications(
    value: object,
    *,
    asset_id: str,
    path_parts: tuple[object, ...],
) -> list[str] | UninterpretedDataAsset:
    if not isinstance(value, list):
        _raise("remote_state.invalid_shape", "classifications must be an array", *path_parts)
    normalized: list[str] = []
    seen: set[str] = set()
    for index, entry in enumerate(value):
        if not isinstance(entry, str) or not entry:
            _raise(
                "remote_state.invalid_shape",
                "classification entry must be a non-empty string",
                *(*path_parts, index),
            )
        if entry in seen:
            return UninterpretedDataAsset(id=asset_id, reason_code=REASON_DUPLICATE_CLASSIFICATION)
        seen.add(entry)
        normalized.append(entry)
    return sorted(normalized)


def _normalize_source(value: object) -> dict[str, Any]:
    if value is None:
        _raise("remote_state.invalid_shape", "explicit null is not allowed", "source")
    obj = _require_object(value, path_parts=("source",))
    _check_unknown_keys(obj, SOURCE_KNOWN, path_parts=("source",))
    normalized: dict[str, Any] = {
        "type": _require_non_empty_string(obj.get("type"), path_parts=("source", "type")),
        "assetId": normalize_uuid_string(obj.get("assetId"))
        or _raise(
            "remote_state.invalid_shape",
            "source.assetId must be a valid UUID",
            "source",
            "assetId",
        ),
        "assetType": _require_non_empty_string(
            obj.get("assetType"), path_parts=("source", "assetType")
        ),
        "fqn": _require_non_empty_string(obj.get("fqn"), path_parts=("source", "fqn")),
        "accountName": _require_non_empty_string(
            obj.get("accountName"), path_parts=("source", "accountName")
        ),
    }
    attrs = obj.get("assetAttributes")
    if not isinstance(attrs, list):
        _raise(
            "remote_state.invalid_shape",
            "source.assetAttributes must be an array",
            "source",
            "assetAttributes",
        )
    normalized_attrs: list[str] = []
    for index, entry in enumerate(attrs):
        if not isinstance(entry, str):
            _raise(
                "remote_state.invalid_shape",
                "source.assetAttributes entries must be strings",
                "source",
                "assetAttributes",
                index,
            )
        normalized_attrs.append(entry)
    normalized["assetAttributes"] = normalized_attrs
    return normalized


def _normalize_schema_entry(value: object, *, path_parts: tuple[object, ...]) -> dict[str, Any]:
    obj = _require_object(value, path_parts=path_parts)
    _check_unknown_keys(obj, SCHEMA_ENTRY_KNOWN, path_parts=path_parts)
    normalized: dict[str, Any] = {
        "name": _require_non_empty_string(obj.get("name"), path_parts=(*path_parts, "name")),
        "type": _require_non_empty_string(obj.get("type"), path_parts=(*path_parts, "type")),
    }
    if "description" in obj:
        normalized["description"] = _optional_non_null_string(
            obj["description"], path_parts=(*path_parts, "description")
        )
    if "classifications" in obj:
        classifications = obj["classifications"]
        if classifications is None:
            _raise(
                "remote_state.invalid_shape",
                "explicit null is not allowed",
                *(*path_parts, "classifications"),
            )
        if not isinstance(classifications, list):
            _raise(
                "remote_state.invalid_shape",
                "schema classifications must be an array",
                *(*path_parts, "classifications"),
            )
        normalized_cls: list[str] = []
        seen: set[str] = set()
        for index, entry in enumerate(classifications):
            if not isinstance(entry, str) or not entry:
                _raise(
                    "remote_state.invalid_shape",
                    "schema classification must be a non-empty string",
                    *(*path_parts, "classifications", index),
                )
            if entry in seen:
                _raise(
                    "remote_state.invalid_shape",
                    "duplicate schema classification",
                    *(*path_parts, "classifications", index),
                )
            seen.add(entry)
            normalized_cls.append(entry)
        normalized["classifications"] = sorted(normalized_cls)
    return normalized


def _normalize_type_properties(
    value: object,
    *,
    asset_type: str,
) -> dict[str, Any]:
    if value is None:
        _raise("remote_state.invalid_shape", "explicit null is not allowed", "typeProperties")
    obj = _require_object(value, path_parts=("typeProperties",))
    if asset_type == "AzureSqlTable":
        _check_unknown_keys(
            obj, AZURE_SQL_TABLE_TYPE_PROPERTIES_KNOWN, path_parts=("typeProperties",)
        )
        format_value = obj.get("format")
        if not isinstance(format_value, str) or format_value not in TYPE_PROPERTIES_FORMAT:
            _raise(
                "remote_state.invalid_shape",
                "typeProperties.format is not a documented enum value",
                "typeProperties",
                "format",
            )
        return {
            "format": format_value,
            "serverEndpoint": _require_non_empty_string(
                obj.get("serverEndpoint"), path_parts=("typeProperties", "serverEndpoint")
            ),
            "databaseName": _require_non_empty_string(
                obj.get("databaseName"), path_parts=("typeProperties", "databaseName")
            ),
            "schemaName": _require_non_empty_string(
                obj.get("schemaName"), path_parts=("typeProperties", "schemaName")
            ),
            "tableName": _require_non_empty_string(
                obj.get("tableName"), path_parts=("typeProperties", "tableName")
            ),
        }
    if asset_type == "ADLSGen2Path":
        _check_unknown_keys(
            obj, ADLS_GEN2_PATH_TYPE_PROPERTIES_KNOWN, path_parts=("typeProperties",)
        )
        return {
            "serverEndpoint": _require_non_empty_string(
                obj.get("serverEndpoint"), path_parts=("typeProperties", "serverEndpoint")
            ),
            "container": _require_non_empty_string(
                obj.get("container"), path_parts=("typeProperties", "container")
            ),
            "folderPath": _require_non_empty_string(
                obj.get("folderPath"), path_parts=("typeProperties", "folderPath")
            ),
            "fileName": _require_non_empty_string(
                obj.get("fileName"), path_parts=("typeProperties", "fileName")
            ),
        }
    _raise("remote_state.invalid_shape", "typeProperties is not allowed for this asset type")
    raise AssertionError("unreachable")


def normalize_data_asset(
    raw: dict[str, Any],
) -> NormalizedDataAsset | UninterpretedDataAsset:
    """Normalize one Data Asset enumerate item."""
    for key in raw:
        if key not in DATA_ASSET_TOP_LEVEL_KNOWN:
            asset_id = normalize_uuid_string(raw.get("id"))
            return UninterpretedDataAsset(
                id=asset_id,
                reason_code=REASON_UNKNOWN_FIELD,
            )

    asset_id = normalize_uuid_string(raw.get("id"))
    if asset_id is None:
        _raise("remote_state.invalid_shape", "Data Asset id must be a valid UUID", "id")

    provisioning_state = _extract_provisioning_state(raw)
    if provisioning_state in {"SoftDeleted", "Unknown"}:
        return UninterpretedDataAsset(id=asset_id, reason_code=REASON_PROVISIONING_BLOCKED)

    name = _require_non_empty_string(raw.get("name"), path_parts=("name",))
    asset_type = raw.get("type")
    if not isinstance(asset_type, str) or asset_type not in DATA_ASSET_TYPES:
        return UninterpretedDataAsset(id=asset_id, reason_code=REASON_UNSUPPORTED_TYPE)

    doc: dict[str, Any] = {
        "name": name,
        "assetType": asset_type,
    }

    if "description" in raw:
        doc["description"] = _optional_non_null_string(
            raw["description"], path_parts=("description",)
        )
    if "openInUrl" in raw:
        doc["openInUrl"] = _require_non_empty_string(raw["openInUrl"], path_parts=("openInUrl",))
    if "source" in raw:
        doc["source"] = _normalize_source(raw["source"])
    if "contacts" in raw:
        contacts_result = _normalize_contacts(raw["contacts"], asset_id=asset_id)
        if isinstance(contacts_result, UninterpretedDataAsset):
            return contacts_result
        if contacts_result:
            doc["contacts"] = contacts_result
    if "classifications" in raw:
        classifications_result = _normalize_classifications(
            raw["classifications"],
            asset_id=asset_id,
            path_parts=("classifications",),
        )
        if isinstance(classifications_result, UninterpretedDataAsset):
            return classifications_result
        doc["classifications"] = classifications_result
    if "schema" in raw:
        schema_raw = raw["schema"]
        if schema_raw is None:
            _raise("remote_state.invalid_shape", "explicit null is not allowed", "schema")
        if not isinstance(schema_raw, list):
            _raise("remote_state.invalid_shape", "schema must be an array", "schema")
        doc["schema"] = [
            _normalize_schema_entry(item, path_parts=("schema", index))
            for index, item in enumerate(schema_raw)
        ]
    if asset_type in {"AzureSqlTable", "ADLSGen2Path"}:
        if "typeProperties" not in raw:
            _raise(
                "remote_state.invalid_shape",
                "typeProperties is required for this asset type",
                "typeProperties",
            )
        doc["typeProperties"] = _normalize_type_properties(
            raw["typeProperties"], asset_type=asset_type
        )

    safety: dict[str, Any] = {}
    if provisioning_state is not None:
        safety["provisioningState"] = provisioning_state

    return NormalizedDataAsset(
        id=asset_id,
        fields=doc,
        safety_properties=safety,
    )
