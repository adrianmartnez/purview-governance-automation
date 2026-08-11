"""Normalize Custom Classification Rule GET responses (fail-closed)."""

from __future__ import annotations

from typing import Any

from purview_governance.finite_double import FiniteDoubleError, canonicalize_finite_double
from purview_governance.remote_state.api_datetime import validate_api_datetime_string
from purview_governance.remote_state.canonical import compute_value_identity
from purview_governance.remote_state.classification_policy import (
    CLASSIFICATION_ACTIONS,
    CLASSIFICATION_RULE_PROPERTIES_KNOWN,
    CLASSIFICATION_RULE_SEPARATELY_MANAGED_FIELDS,
    CLASSIFICATION_RULE_STATUSES,
    CLASSIFICATION_RULE_TOP_LEVEL_KNOWN,
    CLASSIFICATION_RULE_VOLATILE_PROPERTY_FIELDS,
    INT32_MAX,
    INT32_MIN,
    SUPPORTED_CLASSIFICATION_RULE_KIND,
)
from purview_governance.remote_state.errors import RemoteStateError
from purview_governance.remote_state.models import (
    ClassificationRuleSeparatelyManagedProperties,
    NormalizedClassificationRule,
    RegexClassificationPatternRemote,
    UnsupportedConfigurableField,
)
from purview_governance.scanning.names import validate_classification_rule_name


def _raise(code: str, message: str, *path_parts: object) -> None:
    path = "/" + "/".join(str(part) for part in path_parts) if path_parts else None
    raise RemoteStateError(code, message, path=path)


def _require_object(value: object, *, path_parts: tuple[object, ...]) -> dict[str, Any]:
    if not isinstance(value, dict):
        _raise("remote_state.invalid_shape", "expected a JSON object", *path_parts)
    return value  # type: ignore[return-value]


def _reject_unknown_keys(
    mapping: dict[str, Any],
    *,
    known: frozenset[str],
    path_parts: tuple[object, ...],
) -> None:
    for key in mapping:
        if key not in known:
            _raise(
                "remote_state.unknown_field",
                f"unknown field {key!r} is not allowed",
                *path_parts,
                key,
            )


def _normalize_regex_patterns(
    value: object,
    *,
    path_parts: tuple[object, ...],
) -> tuple[RegexClassificationPatternRemote, ...]:
    if value is None:
        _raise(
            "remote_state.invalid_shape",
            "pattern array must not be null",
            *path_parts,
        )
    if not isinstance(value, list):
        _raise(
            "remote_state.invalid_shape",
            "pattern array must be an array",
            *path_parts,
        )
    patterns: list[RegexClassificationPatternRemote] = []
    for index, item in enumerate(value):
        item_parts = (*path_parts, index)
        item_obj = _require_object(item, path_parts=item_parts)
        if set(item_obj) - {"kind", "pattern"}:
            unknown = sorted(set(item_obj) - {"kind", "pattern"})
            _raise(
                "remote_state.unknown_field",
                f"unknown field {unknown[0]!r} is not allowed",
                *item_parts,
                unknown[0],
            )
        if item_obj.get("kind") != "Regex":
            _raise(
                "remote_state.invalid_shape",
                "pattern kind must be Regex",
                *item_parts,
                "kind",
            )
        pattern = item_obj.get("pattern")
        if not isinstance(pattern, str):
            _raise(
                "remote_state.invalid_shape",
                "pattern must be a string",
                *item_parts,
                "pattern",
            )
        patterns.append(RegexClassificationPatternRemote(pattern=pattern))
    return tuple(patterns)


def _optional_patterns(
    properties: dict[str, Any],
    *,
    field_name: str,
) -> tuple[RegexClassificationPatternRemote, ...]:
    if field_name not in properties:
        return ()
    return _normalize_regex_patterns(
        properties[field_name],
        path_parts=("properties", field_name),
    )


def normalize_custom_classification_rule_get(
    body: dict[str, Any],
    *,
    requested_name: str,
) -> NormalizedClassificationRule:
    """Normalize an authoritative Custom Classification Rule GET body."""
    _reject_unknown_keys(
        body,
        known=CLASSIFICATION_RULE_TOP_LEVEL_KNOWN,
        path_parts=(),
    )

    remote_name = body.get("name")
    if remote_name is None:
        _raise("remote_state.identity_mismatch", "GET response is missing name", "name")
    validated_name = validate_classification_rule_name(remote_name)
    if validated_name != requested_name:
        _raise(
            "remote_state.identity_mismatch",
            "GET response name does not match the requested classificationRuleName",
            "name",
        )

    kind = body.get("kind")
    if not isinstance(kind, str):
        _raise(
            "remote_state.invalid_shape",
            "kind must be a string",
            "kind",
        )
    if kind != SUPPORTED_CLASSIFICATION_RULE_KIND:
        _raise(
            "remote_state.unsupported_kind",
            "classification rule kind is not Custom",
            "kind",
        )

    if "id" in body:
        raw_id = body["id"]
        if raw_id is None:
            _raise(
                "remote_state.invalid_shape",
                "id must not be null",
                "id",
            )
        if not isinstance(raw_id, str):
            _raise(
                "remote_state.invalid_shape",
                "id must be a string when present",
                "id",
            )

    properties = _require_object(body.get("properties"), path_parts=("properties",))
    _reject_unknown_keys(
        properties,
        known=CLASSIFICATION_RULE_PROPERTIES_KNOWN,
        path_parts=("properties",),
    )

    for volatile in CLASSIFICATION_RULE_VOLATILE_PROPERTY_FIELDS:
        if volatile not in properties:
            continue
        raw_volatile = properties[volatile]
        if raw_volatile is None:
            _raise(
                "remote_state.invalid_shape",
                f"{volatile} must not be null",
                "properties",
                volatile,
            )
        try:
            validate_api_datetime_string(raw_volatile)
        except ValueError as exc:
            _raise(
                "remote_state.invalid_shape",
                f"{volatile} {exc}",
                "properties",
                volatile,
            )

    classification_name = properties.get("classificationName")
    if not isinstance(classification_name, str):
        if classification_name is None and "classificationName" in properties:
            _raise(
                "remote_state.invalid_shape",
                "classificationName must not be null",
                "properties",
                "classificationName",
            )
        _raise(
            "remote_state.invalid_shape",
            "classificationName must be a string",
            "properties",
            "classificationName",
        )

    if "minimumPercentageMatch" not in properties:
        _raise(
            "remote_state.invalid_shape",
            "minimumPercentageMatch is required",
            "properties",
            "minimumPercentageMatch",
        )
    try:
        minimum_percentage_match = canonicalize_finite_double(properties["minimumPercentageMatch"])
    except FiniteDoubleError as exc:
        _raise(
            "remote_state.invalid_shape",
            exc.message,
            "properties",
            "minimumPercentageMatch",
        )

    rule_status = properties.get("ruleStatus")
    if not isinstance(rule_status, str):
        _raise(
            "remote_state.invalid_shape",
            "ruleStatus must be a string",
            "properties",
            "ruleStatus",
        )
    if rule_status not in CLASSIFICATION_RULE_STATUSES:
        _raise(
            "remote_state.invalid_shape",
            "ruleStatus must be Enabled or Disabled",
            "properties",
            "ruleStatus",
        )

    description: str | None = None
    if "description" in properties:
        raw_description = properties["description"]
        if raw_description is None:
            _raise(
                "remote_state.invalid_shape",
                "description must not be null",
                "properties",
                "description",
            )
        if not isinstance(raw_description, str):
            _raise(
                "remote_state.invalid_shape",
                "description must be a string when present",
                "properties",
                "description",
            )
        description = raw_description

    data_patterns = _optional_patterns(properties, field_name="dataPatterns")
    column_patterns = _optional_patterns(properties, field_name="columnPatterns")

    separately = ClassificationRuleSeparatelyManagedProperties()
    action_present = "classificationAction" in properties
    version_present = "version" in properties
    classification_action: str | None = None
    version: int | None = None

    if action_present:
        action = properties["classificationAction"]
        if action is None:
            _raise(
                "remote_state.invalid_shape",
                "classificationAction must not be null",
                "properties",
                "classificationAction",
            )
        if not isinstance(action, str):
            _raise(
                "remote_state.invalid_shape",
                "classificationAction must be a string",
                "properties",
                "classificationAction",
            )
        if action not in CLASSIFICATION_ACTIONS:
            _raise(
                "remote_state.invalid_shape",
                "classificationAction must be Keep or Delete",
                "properties",
                "classificationAction",
            )
        classification_action = action

    if version_present:
        raw_version = properties["version"]
        if raw_version is None:
            _raise(
                "remote_state.invalid_shape",
                "version must not be null",
                "properties",
                "version",
            )
        if isinstance(raw_version, bool) or not isinstance(raw_version, int):
            _raise(
                "remote_state.invalid_shape",
                "version must be an integer when present",
                "properties",
                "version",
            )
        if raw_version < INT32_MIN or raw_version > INT32_MAX:
            _raise(
                "remote_state.invalid_shape",
                "version must be within int32 range",
                "properties",
                "version",
            )
        version = raw_version

    if action_present or version_present:
        separately = ClassificationRuleSeparatelyManagedProperties(
            classification_action=classification_action,  # type: ignore[arg-type]
            version=version,
        )

    # Future unsupported material hook: none known beyond allowlisted fields today.
    unsupported: tuple[UnsupportedConfigurableField, ...] = ()
    _ = CLASSIFICATION_RULE_SEPARATELY_MANAGED_FIELDS
    _ = compute_value_identity

    return NormalizedClassificationRule(
        name=requested_name,
        kind="Custom",
        classification_name=classification_name,
        minimum_percentage_match=minimum_percentage_match,
        rule_status=rule_status,  # type: ignore[arg-type]
        data_patterns=data_patterns,
        column_patterns=column_patterns,
        description=description,
        separately_managed=separately,
        unsupported_configurable_fields=unsupported,
    )


def extract_classification_rule_list_item(
    item: object,
    *,
    index: int,
) -> tuple[str, str]:
    """Validate a list item enough to extract name and kind."""
    path_base: tuple[object, ...] = ("value", index)
    if not isinstance(item, dict):
        _raise(
            "remote_state.malformed_list_item",
            "list item must be a JSON object",
            *path_base,
        )
    name = item.get("name")
    if not isinstance(name, str):
        _raise(
            "remote_state.malformed_list_item",
            "list item name must be a string",
            *path_base,
            "name",
        )
    validated = validate_classification_rule_name(name)
    kind = item.get("kind")
    if not isinstance(kind, str) or not kind:
        _raise(
            "remote_state.malformed_list_item",
            "list item kind must be a non-empty string",
            *path_base,
            "kind",
        )
    return validated, kind
