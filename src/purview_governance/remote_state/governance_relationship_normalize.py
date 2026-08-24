"""Normalize Unified Catalog governance relationship list items (remote-state/v3)."""

from __future__ import annotations

from typing import Any

from purview_governance.config.diagnostics import classify_unknown_field, json_pointer
from purview_governance.remote_state.api_datetime import validate_api_datetime_string
from purview_governance.remote_state.errors import RemoteStateError
from purview_governance.remote_state.governance_relationship_policy import (
    APPROVED_RELATIONSHIP_TYPES,
    GOVERNANCE_RELATIONSHIP_TARGET_CATEGORIES,
    REASON_INVALID_SHAPE,
    REASON_UNKNOWN_FIELD,
    REASON_UNSUPPORTED_RELATIONSHIP_TYPE,
    REASON_UNSUPPORTED_TARGET_CATEGORY,
    RELATIONSHIP_SYSTEM_DATA_KNOWN,
    RELATIONSHIP_TOP_LEVEL_KNOWN,
)
from purview_governance.remote_state.models_v3 import (
    NormalizedGovernanceRelationship,
    UninterpretedGovernanceRelationship,
)
from purview_governance.uuid_utils import normalize_uuid_string


def _raise(code: str, message: str, *path_parts: object) -> None:
    path = json_pointer(*path_parts) if path_parts else ""
    raise RemoteStateError(code, message, path=path)


def _require_object(value: object, *, path_parts: tuple[object, ...]) -> dict[str, Any]:
    if not isinstance(value, dict):
        _raise(REASON_INVALID_SHAPE, "expected a JSON object", *path_parts)
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
        REASON_UNKNOWN_FIELD,
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


def _validate_system_data(value: object) -> None:
    if value is None:
        _raise(REASON_INVALID_SHAPE, "explicit null is not allowed", "systemData")
    obj = _require_object(value, path_parts=("systemData",))
    _check_unknown_keys(obj, RELATIONSHIP_SYSTEM_DATA_KNOWN, path_parts=("systemData",))
    if "createdAt" in obj and not isinstance(obj["createdAt"], str):
        _raise(
            REASON_INVALID_SHAPE,
            "systemData.createdAt must be a string",
            "systemData",
            "createdAt",
        )
    if "lastModifiedAt" in obj:
        try:
            validate_api_datetime_string(obj["lastModifiedAt"])
        except ValueError as exc:
            _raise(REASON_INVALID_SHAPE, str(exc), "systemData", "lastModifiedAt")
    for field in ("createdBy", "lastModifiedBy"):
        if field in obj and normalize_uuid_string(obj[field]) is None:
            _raise(
                REASON_INVALID_SHAPE,
                "systemData actor must be a valid UUID",
                "systemData",
                field,
            )


def normalize_governance_relationship(
    raw: dict[str, Any],
    *,
    source_type: str,
    source_id: str,
    target_category: str,
) -> NormalizedGovernanceRelationship | UninterpretedGovernanceRelationship:
    """Normalize one relationship list item from an authoritative source enumeration."""
    if target_category not in GOVERNANCE_RELATIONSHIP_TARGET_CATEGORIES:
        _raise(
            REASON_UNSUPPORTED_TARGET_CATEGORY,
            "target category is not supported for governance relationships",
        )

    for key in raw:
        if key not in RELATIONSHIP_TOP_LEVEL_KNOWN:
            return UninterpretedGovernanceRelationship(
                reason_code=REASON_UNKNOWN_FIELD,
                source_type=source_type,
                source_id=source_id,
                target_category=target_category,
            )

    if "systemData" in raw:
        _validate_system_data(raw["systemData"])

    target_id = normalize_uuid_string(raw.get("entityId"))
    if target_id is None:
        _raise(REASON_INVALID_SHAPE, "entityId must be a valid UUID", "entityId")

    relationship_type = raw.get("relationshipType")
    if not isinstance(relationship_type, str):
        _raise(REASON_INVALID_SHAPE, "relationshipType must be a string", "relationshipType")
    if relationship_type not in APPROVED_RELATIONSHIP_TYPES:
        return UninterpretedGovernanceRelationship(
            reason_code=REASON_UNSUPPORTED_RELATIONSHIP_TYPE,
            source_type=source_type,
            source_id=source_id,
            target_category=target_category,
            target_id=target_id,
            relationship_type=relationship_type,
        )

    fields: dict[str, Any] = {}
    if "description" in raw:
        if raw["description"] is None:
            _raise(REASON_INVALID_SHAPE, "explicit null is not allowed", "description")
        if not isinstance(raw["description"], str):
            _raise(REASON_INVALID_SHAPE, "description must be a string", "description")
        fields["description"] = raw["description"]

    return NormalizedGovernanceRelationship(
        source_type=source_type,
        source_id=source_id,
        target_category=target_category,
        target_id=target_id,
        relationship_type=relationship_type,
        fields=fields,
    )
