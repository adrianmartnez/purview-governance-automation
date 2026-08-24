"""Normalize Unified Catalog Data Column query items (remote-state/v3)."""

from __future__ import annotations

from typing import Any

from purview_governance.config.diagnostics import classify_unknown_field, json_pointer
from purview_governance.remote_state.data_column_policy import (
    ASSET_DETAILS_KNOWN,
    COLUMN_DETAILS_KNOWN,
    DATA_COLUMN_TOP_LEVEL_KNOWN,
    DATA_COLUMN_TYPES,
    REASON_UNKNOWN_FIELD,
    REASON_UNSUPPORTED_TYPE,
    SOURCE_KNOWN,
)
from purview_governance.remote_state.errors import RemoteStateError
from purview_governance.remote_state.models_v3 import (
    NormalizedDataColumn,
    UninterpretedDataColumn,
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
        "columnId": normalize_uuid_string(obj.get("columnId"))
        or _raise(
            "remote_state.invalid_shape",
            "source.columnId must be a valid UUID",
            "source",
            "columnId",
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


def _normalize_enrichment_object(
    value: object,
    known: frozenset[str],
    *,
    field_name: str,
) -> dict[str, Any] | None:
    if value is None:
        return None
    obj = _require_object(value, path_parts=(field_name,))
    _check_unknown_keys(obj, known, path_parts=(field_name,))
    normalized: dict[str, Any] = {}
    for key, item in obj.items():
        if key == "assetId":
            if not isinstance(item, str):
                _raise(
                    "remote_state.invalid_shape",
                    f"{field_name}.assetId must be a string",
                    field_name,
                    "assetId",
                )
            normalized["assetId"] = item
        elif key == "isNullable":
            if not isinstance(item, bool):
                _raise(
                    "remote_state.invalid_shape",
                    f"{field_name}.isNullable must be a boolean",
                    field_name,
                    "isNullable",
                )
            normalized["isNullable"] = item
        elif key in {"ordinalPosition", "maxLength", "precision", "scale"}:
            if not isinstance(item, int) or isinstance(item, bool):
                _raise(
                    "remote_state.invalid_shape",
                    f"{field_name}.{key} must be an integer",
                    field_name,
                    key,
                )
            normalized[key] = item
        elif key in {"dataType", "assetType", "fqn", "accountName", "name"}:
            if not isinstance(item, str):
                _raise(
                    "remote_state.invalid_shape",
                    f"{field_name}.{key} must be a string",
                    field_name,
                    key,
                )
            normalized[key] = item
        elif key == "assetAttributes":
            if not isinstance(item, list):
                _raise(
                    "remote_state.invalid_shape",
                    f"{field_name}.assetAttributes must be an array",
                    field_name,
                    "assetAttributes",
                )
            attrs: list[str] = []
            for index, entry in enumerate(item):
                if not isinstance(entry, str):
                    _raise(
                        "remote_state.invalid_shape",
                        "assetAttributes entries must be strings",
                        field_name,
                        "assetAttributes",
                        index,
                    )
                attrs.append(entry)
            normalized["assetAttributes"] = attrs
    return normalized


def normalize_data_column(
    raw: dict[str, Any],
) -> NormalizedDataColumn | UninterpretedDataColumn:
    """Normalize one Data Column query item."""
    for key in raw:
        if key not in DATA_COLUMN_TOP_LEVEL_KNOWN:
            column_id = normalize_uuid_string(raw.get("id"))
            return UninterpretedDataColumn(
                id=column_id,
                reason_code=REASON_UNKNOWN_FIELD,
            )

    column_id = normalize_uuid_string(raw.get("id"))
    if column_id is None:
        _raise("remote_state.invalid_shape", "Data Column id must be a valid UUID", "id")

    if "source" not in raw:
        _raise("remote_state.invalid_shape", "source is required", "source")

    column_type = raw.get("type")
    if not isinstance(column_type, str) or column_type not in DATA_COLUMN_TYPES:
        return UninterpretedDataColumn(id=column_id, reason_code=REASON_UNSUPPORTED_TYPE)

    fields: dict[str, Any] = {
        "columnType": column_type,
        "source": _normalize_source(raw["source"]),
    }
    if "name" in raw:
        if raw["name"] is None:
            _raise("remote_state.invalid_shape", "explicit null is not allowed", "name")
        fields["name"] = _require_non_empty_string(raw["name"], path_parts=("name",))
    if "description" in raw:
        if raw["description"] is None:
            _raise("remote_state.invalid_shape", "explicit null is not allowed", "description")
        if not isinstance(raw["description"], str):
            _raise("remote_state.invalid_shape", "description must be a string", "description")
        fields["description"] = raw["description"]

    if "columnDetails" in raw:
        column_details = raw["columnDetails"]
        if column_details is None:
            fields["columnDetails"] = None
        elif not isinstance(column_details, dict):
            _raise(
                "remote_state.invalid_shape",
                "columnDetails must be an object or null",
                "columnDetails",
            )
        else:
            fields["columnDetails"] = _normalize_enrichment_object(
                column_details,
                COLUMN_DETAILS_KNOWN,
                field_name="columnDetails",
            )

    if "assetDetails" in raw:
        asset_details = raw["assetDetails"]
        if asset_details is None:
            fields["assetDetails"] = None
        elif not isinstance(asset_details, dict):
            _raise(
                "remote_state.invalid_shape",
                "assetDetails must be an object or null",
                "assetDetails",
            )
        else:
            fields["assetDetails"] = _normalize_enrichment_object(
                asset_details,
                ASSET_DETAILS_KNOWN,
                field_name="assetDetails",
            )

    return NormalizedDataColumn(id=column_id, fields=fields)
