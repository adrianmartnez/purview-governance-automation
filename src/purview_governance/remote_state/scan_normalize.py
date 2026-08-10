"""Normalize Scan and Scan Rule Set GET bodies into remote-state/v2 models."""

from __future__ import annotations

from typing import Any, Literal

from purview_governance.config.diagnostics import json_pointer
from purview_governance.remote_state.canonical import compute_value_identity
from purview_governance.remote_state.errors import RemoteStateError
from purview_governance.remote_state.models import (
    NormalizedScan,
    NormalizedScanRuleSet,
    ScanObservedProperties,
    UnsupportedConfigurableField,
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
    SCAN_UNSUPPORTED_NULL_FAIL_PROPERTY_FIELDS,
    SCAN_UNSUPPORTED_NULL_SAFE_PROPERTY_FIELDS,
    SCAN_UNSUPPORTED_NULL_SAFE_TOP_LEVEL_FIELDS,
    SCAN_UNSUPPORTED_PROPERTY_FIELDS,
    SCAN_UNSUPPORTED_TOP_LEVEL_FIELDS,
    SCAN_VOLATILE_PROPERTY_FIELDS,
    SCANNING_RULE_KNOWN,
    SUPPORTED_SCAN_KIND,
    SUPPORTED_SCAN_RULESET_KIND,
    SUPPORTED_SCAN_RULESET_TYPE,
)
from purview_governance.scanning.errors import PurviewDataSourceNameError
from purview_governance.scanning.file_extensions import FILE_EXTENSIONS_TYPE
from purview_governance.scanning.names import (
    validate_data_source_name,
    validate_scan_name,
    validate_scan_ruleset_name,
)

_UnsupportedExpectedType = Literal["object", "string", "boolean", "integer"]

_SCAN_UNSUPPORTED_PROPERTY_EXPECTED_TYPES: dict[str, _UnsupportedExpectedType] = {
    "connectedVia": "object",
    "domain": "string",
    "isLiveViewEnabled": "boolean",
    "isPresetScan": "boolean",
    "logLevel": "string",
    "parallelScanCount": "integer",
    "workers": "integer",
    "businessRuleSetName": "string",
}

_SCAN_UNSUPPORTED_TOP_LEVEL_EXPECTED_TYPES: dict[str, _UnsupportedExpectedType] = {
    "dataSourceIdentifier": "object",
}


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


def _value_matches_expected_type(value: object, expected: _UnsupportedExpectedType) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    return False


def _record_unsupported_configurable(
    container: dict[str, Any],
    field_name: str,
    *,
    path_parts: tuple[object, ...],
    expected_type: _UnsupportedExpectedType,
    null_policy: Literal["safe_absent", "fail"],
    unsupported: list[UnsupportedConfigurableField],
) -> None:
    """Apply per-field null policy and record explicit unsupported values with identity."""
    if field_name not in container:
        return
    value = container[field_name]
    if value is None:
        if null_policy == "safe_absent":
            return
        _raise(
            "remote_state.invalid_shape",
            f"{field_name} must not be null",
            *(*path_parts, field_name),
        )
    if not _value_matches_expected_type(value, expected_type):
        _raise(
            "remote_state.invalid_shape",
            f"{field_name} has an invalid type for unsupported configurable capture",
            *(*path_parts, field_name),
        )
    reject_sensitive_keys(value, path_parts=(*path_parts, field_name))
    unsupported.append(
        UnsupportedConfigurableField(
            path=json_pointer(*path_parts, field_name),
            value_identity=compute_value_identity(value),
        )
    )


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


def _sorted_file_extensions(
    value: object,
    *,
    path_parts: tuple[object, ...],
) -> tuple[str, ...]:
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
        stripped = entry.strip()
        if stripped not in FILE_EXTENSIONS_TYPE:
            _raise(
                "remote_state.invalid_file_extension",
                f"file extension {stripped!r} is not a documented FileExtensionsType value",
                *(*path_parts, index),
            )
        items.append(stripped)
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

    unsupported: list[UnsupportedConfigurableField] = []
    for field_name in sorted(SCAN_UNSUPPORTED_PROPERTY_FIELDS):
        if field_name in SCAN_UNSUPPORTED_NULL_SAFE_PROPERTY_FIELDS:
            null_policy: Literal["safe_absent", "fail"] = "safe_absent"
        elif field_name in SCAN_UNSUPPORTED_NULL_FAIL_PROPERTY_FIELDS:
            null_policy = "fail"
        else:
            _raise(
                "remote_state.invalid_shape",
                f"missing null policy for unsupported field {field_name!r}",
                "properties",
                field_name,
            )
            raise AssertionError("unreachable")
        _record_unsupported_configurable(
            properties,
            field_name,
            path_parts=("properties",),
            expected_type=_SCAN_UNSUPPORTED_PROPERTY_EXPECTED_TYPES[field_name],
            null_policy=null_policy,
            unsupported=unsupported,
        )
    for field_name in sorted(SCAN_UNSUPPORTED_TOP_LEVEL_FIELDS):
        null_policy = (
            "safe_absent" if field_name in SCAN_UNSUPPORTED_NULL_SAFE_TOP_LEVEL_FIELDS else "fail"
        )
        _record_unsupported_configurable(
            body,
            field_name,
            path_parts=(),
            expected_type=_SCAN_UNSUPPORTED_TOP_LEVEL_EXPECTED_TYPES[field_name],
            null_policy=null_policy,
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
        unsupported_configurable_fields=tuple(sorted(unsupported, key=lambda item: item.path)),
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

    unsupported: list[UnsupportedConfigurableField] = []
    if "customFileExtensions" in scanning_rule:
        custom = scanning_rule["customFileExtensions"]
        if custom is not None:
            # Explicit non-null (including []) is unsupported configurable evidence.
            # Do not desired-support; do not unknown_field; do not silently drop.
            reject_sensitive_keys(
                custom,
                path_parts=("properties", "scanningRule", "customFileExtensions"),
            )
            unsupported.append(
                UnsupportedConfigurableField(
                    path="/properties/scanningRule/customFileExtensions",
                    value_identity=compute_value_identity(custom),
                )
            )

    if "fileExtensions" not in scanning_rule:
        _raise(
            "remote_state.invalid_shape",
            "scanningRule.fileExtensions is required",
            "properties",
            "scanningRule",
            "fileExtensions",
        )
    file_extensions = _sorted_file_extensions(
        scanning_rule["fileExtensions"],
        path_parts=("properties", "scanningRule", "fileExtensions"),
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
    if "description" in properties:
        raw_description = properties["description"]
        if raw_description is None:
            description = None
        elif not isinstance(raw_description, str):
            _raise(
                "remote_state.invalid_shape",
                "description must be a string when present",
                "properties",
                "description",
            )
        else:
            # Preserve empty string distinctly from absent/null.
            description = raw_description

    return NormalizedScanRuleSet(
        name=requested_name,
        kind="AzureStorage",
        scan_ruleset_type="Custom",
        file_extensions=file_extensions,
        excluded_system_classifications=excluded,
        included_custom_classification_rule_names=included,
        description=description,
        unsupported_configurable_fields=tuple(sorted(unsupported, key=lambda item: item.path)),
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
            "list item name is not a valid scanRulesetName",
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
