"""Normalize authoritative Data Source GET bodies into remote-state models."""

from __future__ import annotations

from typing import Any

from purview_governance.config.diagnostics import json_pointer
from purview_governance.data_source_endpoint import (
    DataSourceEndpointError,
    validate_data_source_endpoint,
)
from purview_governance.remote_state.errors import RemoteStateError
from purview_governance.remote_state.models import (
    NormalizedDataSource,
    ObservedProperties,
    UnknownLegacyMovingState,
)
from purview_governance.remote_state.policy import (
    COLLECTION_KNOWN,
    COLLECTION_TYPE_EXPECTED,
    CREATION_TYPES,
    DATA_USE_GOVERNANCE_VALUES,
    LEGACY_MOVING_RAW,
    MOVING_STATES_TEXTUAL,
    PROPERTIES_KNOWN,
    SUPPORTED_KIND,
    TOP_LEVEL_KNOWN,
    VOLATILE_COLLECTION_FIELDS,
    VOLATILE_PROPERTY_FIELDS,
)
from purview_governance.scanning.errors import PurviewDataSourceNameError
from purview_governance.scanning.names import validate_data_source_name
from purview_governance.sensitive import is_sensitive_field_name


def _raise(code: str, message: str, *path_parts: object) -> None:
    path = json_pointer(*path_parts) if path_parts else ""
    raise RemoteStateError(code, message, path=path)


def reject_sensitive_keys(value: object, *, path_parts: tuple[object, ...] = ()) -> None:
    """Recursively reject sensitive field names before materialization."""
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            child_path = (*path_parts, key_text)
            if is_sensitive_field_name(key_text):
                _raise(
                    "remote_state.sensitive_field",
                    f"sensitive field {key_text!r} is not allowed in remote state",
                    *child_path,
                )
            reject_sensitive_keys(child, path_parts=child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reject_sensitive_keys(child, path_parts=(*path_parts, index))


def normalize_endpoint_value(raw: object, *, path_parts: tuple[object, ...]) -> str:
    """Validate material Data Source endpoint (HTTPS; no userinfo/query/fragment)."""
    validation_failed = False
    try:
        return validate_data_source_endpoint(raw)
    except DataSourceEndpointError:
        validation_failed = True
    if validation_failed:
        _raise(
            "remote_state.invalid_endpoint",
            "Data Source endpoint is invalid or unsafe",
            *path_parts,
        )
    raise AssertionError("unreachable")


def _require_object(value: object, *, path_parts: tuple[object, ...]) -> dict[str, Any]:
    if not isinstance(value, dict):
        _raise(
            "remote_state.invalid_shape",
            "expected a JSON object",
            *path_parts,
        )
    assert isinstance(value, dict)
    return value


def _check_unknown_keys(
    obj: dict[str, Any],
    known: frozenset[str],
    *,
    path_parts: tuple[object, ...],
) -> None:
    for key in obj:
        if key not in known:
            _raise(
                "remote_state.unknown_field",
                f"unknown field {key!r} is not allowed",
                *(*path_parts, key),
            )


def _validate_optional_string(
    value: object,
    *,
    path_parts: tuple[object, ...],
) -> str:
    if not isinstance(value, str):
        _raise(
            "remote_state.invalid_observed_property",
            "observed property must be a string",
            *path_parts,
        )
    return value


def _normalize_collection(
    collection: object,
    *,
    path_parts: tuple[object, ...],
) -> str:
    coll = _require_object(collection, path_parts=path_parts)
    _check_unknown_keys(coll, COLLECTION_KNOWN, path_parts=path_parts)
    if "referenceName" not in coll:
        _raise(
            "remote_state.invalid_shape",
            "collection.referenceName is required",
            *(*path_parts, "referenceName"),
        )
    ref = coll["referenceName"]
    if not isinstance(ref, str) or not ref.strip():
        _raise(
            "remote_state.invalid_shape",
            "collection.referenceName must be a non-empty string",
            *(*path_parts, "referenceName"),
        )
    if "type" in coll:
        coll_type = coll["type"]
        if coll_type != COLLECTION_TYPE_EXPECTED:
            _raise(
                "remote_state.invalid_collection_type",
                f"collection.type must be {COLLECTION_TYPE_EXPECTED!r}",
                *(*path_parts, "type"),
            )
    if "lastModifiedAt" in coll:
        ts = coll["lastModifiedAt"]
        if not isinstance(ts, str):
            _raise(
                "remote_state.invalid_shape",
                "collection.lastModifiedAt must be a string",
                *(*path_parts, "lastModifiedAt"),
            )
        # Volatile: validated then discarded.
        _ = VOLATILE_COLLECTION_FIELDS
    return ref.strip()


def _normalize_moving_state(
    value: object,
    *,
    path_parts: tuple[object, ...],
) -> str | UnknownLegacyMovingState:
    if not isinstance(value, str):
        _raise(
            "remote_state.invalid_collection_moving_state",
            "dataSourceCollectionMovingState must be a string",
            *path_parts,
        )
    if value in MOVING_STATES_TEXTUAL:
        return value
    if value == LEGACY_MOVING_RAW:
        # Official Get example wire quirk — never mapped to Active.
        return UnknownLegacyMovingState(raw="0")
    _raise(
        "remote_state.invalid_collection_moving_state",
        "dataSourceCollectionMovingState is not a documented textual enum value",
        *path_parts,
    )
    raise AssertionError("unreachable")


def _normalize_observed(
    properties: dict[str, Any],
    *,
    observed_id: str | None,
    path_prefix: tuple[object, ...],
) -> ObservedProperties:
    optional_strings = {
        "resourceGroup": "resource_group",
        "subscriptionId": "subscription_id",
        "location": "location",
        "resourceName": "resource_name",
        "resourceId": "resource_id",
    }
    kwargs: dict[str, str | None] = {
        "resource_group": None,
        "subscription_id": None,
        "location": None,
        "resource_name": None,
        "resource_id": None,
        "data_use_governance": None,
        "observed_id": observed_id,
    }
    for wire_name, attr in optional_strings.items():
        if wire_name not in properties:
            continue
        kwargs[attr] = _validate_optional_string(
            properties[wire_name],
            path_parts=(*path_prefix, wire_name),
        )
    if "dataUseGovernance" in properties:
        dug = properties["dataUseGovernance"]
        if not isinstance(dug, str) or dug not in DATA_USE_GOVERNANCE_VALUES:
            _raise(
                "remote_state.invalid_observed_property",
                "dataUseGovernance is not a documented enum value",
                *(*path_prefix, "dataUseGovernance"),
            )
        kwargs["data_use_governance"] = dug
    return ObservedProperties(**kwargs)  # type: ignore[arg-type]


def normalize_azure_storage_get(
    body: dict[str, Any],
    *,
    requested_name: str,
) -> NormalizedDataSource:
    """Normalize an authoritative AzureStorage GET body for requested_name."""
    reject_sensitive_keys(body)
    _check_unknown_keys(body, TOP_LEVEL_KNOWN, path_parts=())

    if "name" not in body:
        _raise(
            "remote_state.identity_mismatch",
            "GET response is missing name",
            "name",
        )
    remote_name = body["name"]
    if not isinstance(remote_name, str):
        _raise(
            "remote_state.identity_mismatch",
            "GET response name must be a string",
            "name",
        )
    try:
        validated_remote = validate_data_source_name(remote_name)
    except PurviewDataSourceNameError:
        _raise(
            "remote_state.identity_mismatch",
            "GET response name is not a valid dataSourceName",
            "name",
        )
        raise AssertionError("unreachable") from None
    if validated_remote != requested_name:
        _raise(
            "remote_state.identity_mismatch",
            "GET response name does not match the requested dataSourceName",
            "name",
        )

    if "kind" not in body:
        _raise(
            "remote_state.missing_kind",
            "GET response is missing kind",
            "kind",
        )
    kind = body["kind"]
    if not isinstance(kind, str):
        _raise(
            "remote_state.invalid_kind",
            "kind must be a string",
            "kind",
        )
    if kind != SUPPORTED_KIND:
        # Caller should route unsupported kinds to uninterpreted accounting.
        _raise(
            "remote_state.unsupported_kind",
            f"kind {kind!r} is not supported by the v1 AzureStorage vertical slice",
            "kind",
        )

    if "creationType" not in body:
        _raise(
            "remote_state.missing_creation_type",
            "creationType is required for safe ownership interpretation",
            "creationType",
        )
    creation_type = body["creationType"]
    if not isinstance(creation_type, str) or creation_type not in CREATION_TYPES:
        _raise(
            "remote_state.invalid_creation_type",
            "creationType is not a documented enum value",
            "creationType",
        )

    if "properties" not in body:
        _raise(
            "remote_state.invalid_shape",
            "properties object is required",
            "properties",
        )
    properties = _require_object(body["properties"], path_parts=("properties",))
    _check_unknown_keys(properties, PROPERTIES_KNOWN, path_parts=("properties",))

    if "scans" in body:
        scans = body["scans"]
        if not isinstance(scans, list):
            _raise(
                "remote_state.invalid_shape",
                "scans must be an array when present",
                "scans",
            )
        if len(scans) > 0:
            _raise(
                "remote_state.nested_scans_unsupported",
                "non-empty embedded scans are not supported for safe remote-state capture",
                "scans",
            )
        # Empty scans is canonical-equivalent to absent (no artifact field).

    for volatile in VOLATILE_PROPERTY_FIELDS:
        if volatile in properties and not isinstance(properties[volatile], str):
            _raise(
                "remote_state.invalid_shape",
                f"{volatile} must be a string",
                "properties",
                volatile,
            )

    if "endpoint" not in properties:
        _raise(
            "remote_state.invalid_shape",
            "properties.endpoint is required",
            "properties",
            "endpoint",
        )
    endpoint = normalize_endpoint_value(
        properties["endpoint"],
        path_parts=("properties", "endpoint"),
    )

    if "collection" not in properties:
        _raise(
            "remote_state.invalid_shape",
            "properties.collection is required",
            "properties",
            "collection",
        )
    collection_ref = _normalize_collection(
        properties["collection"],
        path_parts=("properties", "collection"),
    )

    if "dataSourceCollectionMovingState" not in properties:
        _raise(
            "remote_state.missing_collection_moving_state",
            "dataSourceCollectionMovingState is required for safe interpretation",
            "properties",
            "dataSourceCollectionMovingState",
        )
    moving = _normalize_moving_state(
        properties["dataSourceCollectionMovingState"],
        path_parts=("properties", "dataSourceCollectionMovingState"),
    )

    observed_id: str | None = None
    if "id" in body:
        raw_id = body["id"]
        if not isinstance(raw_id, str):
            _raise(
                "remote_state.invalid_observed_property",
                "id must be a string when present",
                "id",
            )
        observed_id = raw_id

    observed = _normalize_observed(
        properties,
        observed_id=observed_id,
        path_prefix=("properties",),
    )

    return NormalizedDataSource(
        name=requested_name,
        kind="AzureStorage",
        creation_type=creation_type,  # type: ignore[arg-type]
        endpoint=endpoint,
        collection_reference_name=collection_ref,
        collection_moving_state=moving,  # type: ignore[arg-type]
        observed=observed,
    )


def extract_list_item_name(item: object, *, index: int) -> str:
    """Validate a list item enough to extract a safe dataSourceName."""
    path_base: tuple[object, ...] = ("value", index)
    if not isinstance(item, dict):
        _raise(
            "remote_state.malformed_list_item",
            "list item must be a JSON object",
            *path_base,
        )
    assert isinstance(item, dict)
    reject_sensitive_keys(item, path_parts=path_base)
    if "name" not in item:
        _raise(
            "remote_state.malformed_list_item",
            "list item is missing name",
            *(*path_base, "name"),
        )
    name = item["name"]
    if not isinstance(name, str):
        _raise(
            "remote_state.malformed_list_item",
            "list item name must be a string",
            *(*path_base, "name"),
        )
    try:
        return validate_data_source_name(name)
    except PurviewDataSourceNameError:
        _raise(
            "remote_state.malformed_list_item",
            "list item name is not a valid dataSourceName",
            *(*path_base, "name"),
        )
        raise AssertionError("unreachable") from None
