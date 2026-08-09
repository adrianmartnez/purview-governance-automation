"""Schema validation and diagnostic mapping for governance config."""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from purview_governance.config.diagnostics import (
    ConfigDiagnostic,
    ConfigValidationError,
    classify_unknown_field,
    json_pointer,
)
from purview_governance.config.schema import load_v1_schema

SUPPORTED_API_VERSION = "purview-governance-config/v1"


def _path_from_error(error: ValidationError) -> str:
    parts: list[object] = list(error.absolute_path)
    return json_pointer(*parts) if parts else ""


def _schema_property_names(error: ValidationError) -> set[str]:
    if isinstance(error.schema, dict):
        props = error.schema.get("properties")
        if isinstance(props, dict):
            return {str(key) for key in props}
    return set()


def _collect_additional_property_diagnostics(
    error: ValidationError,
) -> list[ConfigDiagnostic]:
    """Expand additionalProperties errors into one diagnostic per unexpected key."""
    schema_props = _schema_property_names(error)
    if not isinstance(error.instance, dict):
        return [
            ConfigDiagnostic(
                code="config.unknown_field",
                path=_path_from_error(error),
                message="unknown field is not allowed",
            )
        ]

    extras = [str(key) for key in error.instance if key not in schema_props]
    if not extras:
        return [
            ConfigDiagnostic(
                code="config.unknown_field",
                path=_path_from_error(error),
                message="unknown field is not allowed",
            )
        ]

    diagnostics: list[ConfigDiagnostic] = []
    for field_name in extras:
        code = classify_unknown_field(field_name)
        field_path = json_pointer(*[*error.absolute_path, field_name])
        if code == "config.secret_field_forbidden":
            message = f"credential material field {field_name!r} is not allowed in configuration"
        else:
            message = f"unknown field {field_name!r} is not allowed"
        diagnostics.append(ConfigDiagnostic(code=code, path=field_path, message=message))
    return diagnostics


def _collect_required_diagnostics(error: ValidationError) -> list[ConfigDiagnostic]:
    """Map required-property failures without parsing jsonschema message text."""
    required_names = error.validator_value
    instance = error.instance
    if not isinstance(required_names, list) or not isinstance(instance, dict):
        return [
            ConfigDiagnostic(
                code="config.unknown_field",
                path=_path_from_error(error),
                message="required field is missing",
            )
        ]

    missing = [name for name in required_names if isinstance(name, str) and name not in instance]
    if not missing:
        return [
            ConfigDiagnostic(
                code="config.unknown_field",
                path=_path_from_error(error),
                message="required field is missing",
            )
        ]

    return [
        ConfigDiagnostic(
            code="config.unknown_field",
            path=json_pointer(*[*error.absolute_path, name]),
            message=f"required field {name!r} is missing",
        )
        for name in missing
    ]


def _map_validation_error(error: ValidationError) -> list[ConfigDiagnostic]:
    path = _path_from_error(error)
    validator = error.validator

    if validator == "required":
        return _collect_required_diagnostics(error)

    if validator == "const" and list(error.absolute_path) == ["apiVersion"]:
        return [
            ConfigDiagnostic(
                code="config.unsupported_version",
                path=path or json_pointer("apiVersion"),
                message=f"unsupported apiVersion; expected {SUPPORTED_API_VERSION!r}",
            )
        ]

    if validator == "const" and list(error.absolute_path)[:1] == ["authentication"]:
        return [
            ConfigDiagnostic(
                code="config.unknown_field",
                path=path,
                message="unsupported authentication strategy",
            )
        ]

    if validator == "const" and list(error.absolute_path)[-1:] == ["kind"]:
        return [
            ConfigDiagnostic(
                code="config.unsupported_data_source_kind",
                path=path,
                message="unsupported Data Source kind; v1 supports only AzureStorage",
            )
        ]

    if validator == "const" and list(error.absolute_path)[-1:] == ["type"]:
        return [
            ConfigDiagnostic(
                code="config.unknown_field",
                path=path,
                message="unsupported resource type; v1 supports only type dataSource",
            )
        ]

    if list(error.absolute_path) == ["apiVersion"]:
        return [
            ConfigDiagnostic(
                code="config.unsupported_version",
                path=path or json_pointer("apiVersion"),
                message=f"unsupported apiVersion; expected {SUPPORTED_API_VERSION!r}",
            )
        ]

    return [
        ConfigDiagnostic(
            code="config.invalid_syntax",
            path=path,
            message="configuration does not match the purview-governance-config/v1 schema",
        )
    ]


def _dedupe_diagnostics(diagnostics: list[ConfigDiagnostic]) -> list[ConfigDiagnostic]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[ConfigDiagnostic] = []
    for diagnostic in diagnostics:
        identity = (diagnostic.code, diagnostic.path, diagnostic.message)
        if identity in seen:
            continue
        seen.add(identity)
        unique.append(diagnostic)
    return unique


def validate_document(document: dict[str, Any]) -> dict[str, Any]:
    """Validate a raw document against the packaged v1 schema."""
    if not isinstance(document, dict):
        raise ConfigValidationError(
            (
                ConfigDiagnostic(
                    code="config.invalid_syntax",
                    path="",
                    message="configuration document must be an object",
                ),
            )
        )

    api_version = document.get("apiVersion")
    version_diagnostic: ConfigDiagnostic | None = None
    if "apiVersion" in document and api_version != SUPPORTED_API_VERSION:
        version_diagnostic = ConfigDiagnostic(
            code="config.unsupported_version",
            path=json_pointer("apiVersion"),
            message=f"unsupported apiVersion; expected {SUPPORTED_API_VERSION!r}",
        )

    schema = load_v1_schema()
    validator = Draft202012Validator(schema)
    diagnostics: list[ConfigDiagnostic] = []
    if version_diagnostic is not None:
        diagnostics.append(version_diagnostic)

    for error in sorted(validator.iter_errors(document), key=lambda e: list(e.absolute_path)):
        if (
            version_diagnostic is not None
            and error.validator == "const"
            and list(error.absolute_path) == ["apiVersion"]
        ):
            continue
        if error.validator == "additionalProperties":
            diagnostics.extend(_collect_additional_property_diagnostics(error))
        else:
            diagnostics.extend(_map_validation_error(error))

    diagnostics.extend(_duplicate_data_source_name_diagnostics(document))
    diagnostics = _dedupe_diagnostics(diagnostics)
    if diagnostics:
        raise ConfigValidationError(diagnostics)
    return document


def _duplicate_data_source_name_diagnostics(
    document: dict[str, Any],
) -> list[ConfigDiagnostic]:
    """Reject duplicate desired Data Source names (no last-wins / silent dedupe)."""
    resources = document.get("resources")
    if not isinstance(resources, list):
        return []
    seen: dict[str, int] = {}
    diagnostics: list[ConfigDiagnostic] = []
    for index, item in enumerate(resources):
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str):
            continue
        if name in seen:
            diagnostics.append(
                ConfigDiagnostic(
                    code="config.duplicate_data_source_name",
                    path=json_pointer("resources", index, "name"),
                    message=(
                        f"duplicate Data Source name {name!r}; "
                        f"first seen at /resources/{seen[name]}/name"
                    ),
                )
            )
        else:
            seen[name] = index
    return diagnostics
