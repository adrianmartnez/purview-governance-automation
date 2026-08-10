"""Normalize Scan and Scan Rule Set GET bodies into remote-state/v2 models."""

from __future__ import annotations

from typing import Any

from purview_governance.config.diagnostics import json_pointer
from purview_governance.remote_state.errors import RemoteStateError
from purview_governance.remote_state.models import (
    NormalizedScan,
    NormalizedScanRuleSet,
    ScanObservedProperties,
)
from purview_governance.remote_state.normalize import reject_sensitive_keys
from purview_governance.remote_state.policy import (
    COLLECTION_KNOWN,
    COLLECTION_TYPE_EXPECTED,
    CREATION_TYPES,
    VOLATILE_COLLECTION_FIELDS,
)
from purview_governance.remote_state.scan_policy import (
    SCAN_PROPERTIES_KNOWN,
    SCAN_RULESET_PROPERTIES_KNOWN,
    SCAN_RULESET_TOP_LEVEL_KNOWN,
    SCAN_RULESET_TYPES,
    SCAN_RULESET_VOLATILE_PROPERTY_FIELDS,
    SCAN_TOP_LEVEL_KNOWN,
    SCAN_UNSUPPORTED_PROPERTY_FIELDS,
    SCAN_UNSUPPORTED_TOP_LEVEL_FIELDS,
    SCAN_VOLATILE_PROPERTY_FIELDS,
    SCANNING_RULE_KNOWN,
    SUPPORTED_SCAN_KIND,
    SUPPORTED_SCAN_RULESET_KIND,
    SUPPORTED_SCAN_RULESET_TYPE,
)
from purview_governance.scanning.errors import PurviewDataSourceNameError
from purview_governance.scanning.names import (
    validate_data_source_name,
    validate_scan_name,
    validate_scan_ruleset_name,
)


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
        _ = VOLATILE_COLLECTION_FIELDS
    return ref.strip()


def _record_unsupported_if_present(
    container: dict[str, Any],
    field_name: str,
    *,
    path_parts: tuple[object, ...],
    unsupported: list[str],
) -> None:
    """Absent or wire-valid null => SAFE ABSENT; any other value => unsupported."""
    if field_name not in container:
        return
    if container[field_name] is None:
        return
    unsupported.append(json_pointer(*path_parts, field_name))


def _sorted_string_list(
    value: object,
    *,
    path_parts: tuple[object, ...],
    allow_null_as_empty: bool,
) -> tuple[str, ...]:
    if value is None and allow_null_as_empty:
        return ()
    if not isinstance(value, list):
        _raise(
            "remote_state.invalid_shape",
            "expected a string array",
            *path_parts,
        )
    items: list[str] = []
    for index, entry in enumerate(value):
        if not isinstance(entry, str) or not entry.strip():
            _raise(
                "remote_state.invalid_shape",
                "array entries must be non-empty strings",
                *(*path_parts, index),
            )
        items.append(entry.strip())
    return tuple(sorted(items))


def normalize_azure_storage_msi_scan_get(
    body: dict[str, Any],
    *,
    requested_data_source_name: str,
    requested_scan_name: str,
) -> NormalizedScan:
    """Normalize an authoritative AzureStorageMsi Scan GET body."""
    reject_sensitive_keys(body)
    _check_unknown_keys(body, SCAN_TOP_LEVEL_KNOWN, path_parts=())

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
        validated_name = validate_scan_name(remote_name)
    except PurviewDataSourceNameError:
        _raise(
            "remote_state.identity_mismatch",
            "GET response name is not a valid scanName",
            "name",
        )
        raise AssertionError("unreachable") from None
    if validated_name != requested_scan_name:
        _raise(
            "remote_state.identity_mismatch",
            "GET response name does not match the requested scanName",
            "name",
        )

    if "dataSourceName" not in body:
        _raise(
            "remote_state.identity_mismatch",
            "GET response is missing dataSourceName",
            "dataSourceName",
        )
    remote_parent = body["dataSourceName"]
    if not isinstance(remote_parent, str):
        _raise(
            "remote_state.identity_mismatch",
            "GET response dataSourceName must be a string",
            "dataSourceName",
        )
    try:
        validated_parent = validate_data_source_name(remote_parent)
    except PurviewDataSourceNameError:
        _raise(
            "remote_state.identity_mismatch",
            "GET response dataSourceName is not a valid dataSourceName",
            "dataSourceName",
        )
        raise AssertionError("unreachable") from None
    if validated_parent != requested_data_source_name:
        _raise(
            "remote_state.identity_mismatch",
            "GET response dataSourceName does not match the requested dataSourceName",
            "dataSourceName",
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
    if kind != SUPPORTED_SCAN_KIND:
        _raise(
            "remote_state.unsupported_kind",
            f"kind {kind!r} is not supported by the AzureStorageMsi scan vertical slice",
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
    _check_unknown_keys(properties, SCAN_PROPERTIES_KNOWN, path_parts=("properties",))

    for volatile in SCAN_VOLATILE_PROPERTY_FIELDS:
        if (
            volatile in properties
            and properties[volatile] is not None
            and not isinstance(properties[volatile], str)
        ):
            _raise(
                "remote_state.invalid_shape",
                f"{volatile} must be a string",
                "properties",
                volatile,
            )

    if (
        "lastRunResult" in body
        and body["lastRunResult"] is not None
        and not isinstance(body["lastRunResult"], dict)
    ):
        _raise(
            "remote_state.invalid_shape",
            "lastRunResult must be an object when present",
            "lastRunResult",
        )

    unsupported: list[str] = []
    for field_name in sorted(SCAN_UNSUPPORTED_PROPERTY_FIELDS):
        _record_unsupported_if_present(
            properties,
            field_name,
            path_parts=("properties",),
            unsupported=unsupported,
        )
    for field_name in sorted(SCAN_UNSUPPORTED_TOP_LEVEL_FIELDS):
        _record_unsupported_if_present(
            body,
            field_name,
            path_parts=(),
            unsupported=unsupported,
        )

    if "scanRulesetName" not in properties:
        _raise(
            "remote_state.invalid_shape",
            "properties.scanRulesetName is required",
            "properties",
            "scanRulesetName",
        )
    scan_ruleset_name = properties["scanRulesetName"]
    if not isinstance(scan_ruleset_name, str) or not scan_ruleset_name.strip():
        _raise(
            "remote_state.invalid_shape",
            "properties.scanRulesetName must be a non-empty string",
            "properties",
            "scanRulesetName",
        )

    if "scanRulesetType" not in properties:
        _raise(
            "remote_state.invalid_shape",
            "properties.scanRulesetType is required",
            "properties",
            "scanRulesetType",
        )
    scan_ruleset_type = properties["scanRulesetType"]
    if not isinstance(scan_ruleset_type, str) or scan_ruleset_type not in SCAN_RULESET_TYPES:
        _raise(
            "remote_state.invalid_shape",
            "properties.scanRulesetType must be System or Custom",
            "properties",
            "scanRulesetType",
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

    observed_id: str | None = None
    if "id" in body and body["id"] is not None:
        raw_id = body["id"]
        if not isinstance(raw_id, str):
            _raise(
                "remote_state.invalid_observed_property",
                "id must be a string when present",
                "id",
            )
        observed_id = raw_id

    scan_id: str | None = None
    if "scanId" in body and body["scanId"] is not None:
        raw_scan_id = body["scanId"]
        if not isinstance(raw_scan_id, str):
            _raise(
                "remote_state.invalid_observed_property",
                "scanId must be a string when present",
                "scanId",
            )
        scan_id = raw_scan_id

    return NormalizedScan(
        name=requested_scan_name,
        data_source_name=requested_data_source_name,
        kind="AzureStorageMsi",
        creation_type=creation_type,  # type: ignore[arg-type]
        scan_ruleset_name=scan_ruleset_name.strip(),
        scan_ruleset_type=scan_ruleset_type,  # type: ignore[arg-type]
        collection_reference_name=collection_ref,
        unsupported_configurable_fields=tuple(unsupported),
        observed=ScanObservedProperties(observed_id=observed_id, scan_id=scan_id),
    )


def normalize_custom_azure_storage_scan_ruleset_get(
    body: dict[str, Any],
    *,
    requested_name: str,
) -> NormalizedScanRuleSet:
    """Normalize a Custom AzureStorage Scan Rule Set GET from /scan/scanrulesets."""
    reject_sensitive_keys(body)
    _check_unknown_keys(body, SCAN_RULESET_TOP_LEVEL_KNOWN, path_parts=())

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
        validated_name = validate_scan_ruleset_name(remote_name)
    except PurviewDataSourceNameError:
        _raise(
            "remote_state.identity_mismatch",
            "GET response name is not a valid scanRulesetName",
            "name",
        )
        raise AssertionError("unreachable") from None
    if validated_name != requested_name:
        _raise(
            "remote_state.identity_mismatch",
            "GET response name does not match the requested scanRulesetName",
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
    if kind != SUPPORTED_SCAN_RULESET_KIND:
        _raise(
            "remote_state.unsupported_kind",
            f"kind {kind!r} is not supported by the Custom AzureStorage scan ruleset slice",
            "kind",
        )

    # Custom endpoint context: absent scanRulesetType is treated as Custom.
    # Explicit non-Custom values are unsupported for this vertical.
    if "scanRulesetType" in body and body["scanRulesetType"] is not None:
        scan_ruleset_type = body["scanRulesetType"]
        if not isinstance(scan_ruleset_type, str):
            _raise(
                "remote_state.invalid_shape",
                "scanRulesetType must be a string",
                "scanRulesetType",
            )
        if scan_ruleset_type != SUPPORTED_SCAN_RULESET_TYPE:
            _raise(
                "remote_state.unsupported_scan_ruleset_type",
                "only Custom scanRulesetType is supported from /scan/scanrulesets",
                "scanRulesetType",
            )
    else:
        scan_ruleset_type = SUPPORTED_SCAN_RULESET_TYPE

    if "id" in body and body["id"] is not None and not isinstance(body["id"], str):
        _raise(
            "remote_state.invalid_observed_property",
            "id must be a string when present",
            "id",
        )
    if "status" in body and body["status"] is not None and not isinstance(body["status"], str):
        _raise(
            "remote_state.invalid_shape",
            "status must be a string when present",
            "status",
        )
    if "version" in body and body["version"] is not None:
        version = body["version"]
        if isinstance(version, bool) or not isinstance(version, int):
            _raise(
                "remote_state.invalid_shape",
                "version must be an integer when present",
                "version",
            )

    if "properties" not in body:
        _raise(
            "remote_state.invalid_shape",
            "properties object is required",
            "properties",
        )
    properties = _require_object(body["properties"], path_parts=("properties",))
    _check_unknown_keys(
        properties,
        SCAN_RULESET_PROPERTIES_KNOWN,
        path_parts=("properties",),
    )

    for volatile in SCAN_RULESET_VOLATILE_PROPERTY_FIELDS:
        if (
            volatile in properties
            and properties[volatile] is not None
            and not isinstance(properties[volatile], str)
        ):
            _raise(
                "remote_state.invalid_shape",
                f"{volatile} must be a string",
                "properties",
                volatile,
            )

    if "scanningRule" not in properties:
        _raise(
            "remote_state.invalid_shape",
            "properties.scanningRule is required",
            "properties",
            "scanningRule",
        )
    scanning_rule = _require_object(
        properties["scanningRule"],
        path_parts=("properties", "scanningRule"),
    )
    _check_unknown_keys(
        scanning_rule,
        SCANNING_RULE_KNOWN,
        path_parts=("properties", "scanningRule"),
    )
    if "fileExtensions" not in scanning_rule:
        _raise(
            "remote_state.invalid_shape",
            "scanningRule.fileExtensions is required",
            "properties",
            "scanningRule",
            "fileExtensions",
        )
    file_extensions = _sorted_string_list(
        scanning_rule["fileExtensions"],
        path_parts=("properties", "scanningRule", "fileExtensions"),
        allow_null_as_empty=False,
    )

    excluded = _sorted_string_list(
        properties.get("excludedSystemClassifications"),
        path_parts=("properties", "excludedSystemClassifications"),
        allow_null_as_empty=True,
    )
    included = _sorted_string_list(
        properties.get("includedCustomClassificationRuleNames"),
        path_parts=("properties", "includedCustomClassificationRuleNames"),
        allow_null_as_empty=True,
    )

    description: str | None = None
    if "description" in properties and properties["description"] is not None:
        raw_description = properties["description"]
        if not isinstance(raw_description, str):
            _raise(
                "remote_state.invalid_shape",
                "description must be a string when present",
                "properties",
                "description",
            )
        description = raw_description

    return NormalizedScanRuleSet(
        name=requested_name,
        kind="AzureStorage",
        scan_ruleset_type="Custom",
        file_extensions=file_extensions,
        excluded_system_classifications=excluded,
        included_custom_classification_rule_names=included,
        description=description,
    )


def extract_scan_list_item_name(item: object, *, index: int) -> str:
    """Validate a scan list item enough to extract a safe scanName."""
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
        return validate_scan_name(name)
    except PurviewDataSourceNameError:
        _raise(
            "remote_state.malformed_list_item",
            "list item name is not a valid scanName",
            *(*path_base, "name"),
        )
        raise AssertionError("unreachable") from None


def extract_scan_ruleset_list_item_name(item: object, *, index: int) -> str:
    """Validate a scan ruleset list item enough to extract a safe name."""
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
        return validate_scan_ruleset_name(name)
    except PurviewDataSourceNameError:
        _raise(
            "remote_state.malformed_list_item",
            "list item name is not a valid scanRulesetName",
            *(*path_base, "name"),
        )
        raise AssertionError("unreachable") from None
