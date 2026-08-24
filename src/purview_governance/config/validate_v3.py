"""Schema validation and semantic checks for governance config v3."""

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
from purview_governance.config.models_v3 import (
    CONFIG_API_VERSION_V3,
    MAX_BUSINESS_DOMAINS,
    MAX_HIERARCHY_DEPTH,
)
from purview_governance.config.schema import load_v3_schema
from purview_governance.uuid_utils import normalize_uuid_string


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
                message=f"unsupported apiVersion; expected {CONFIG_API_VERSION_V3!r}",
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

    if validator == "const" and list(error.absolute_path)[-1:] == ["surface"]:
        return [
            ConfigDiagnostic(
                code="config.unknown_field",
                path=path,
                message="unsupported target surface",
            )
        ]

    if validator == "const" and list(error.absolute_path)[-1:] == ["type"]:
        return [
            ConfigDiagnostic(
                code="config.unknown_field",
                path=path,
                message="unsupported resource type",
            )
        ]

    if list(error.absolute_path) == ["apiVersion"]:
        return [
            ConfigDiagnostic(
                code="config.unsupported_version",
                path=path or json_pointer("apiVersion"),
                message=f"unsupported apiVersion; expected {CONFIG_API_VERSION_V3!r}",
            )
        ]

    return [
        ConfigDiagnostic(
            code="config.invalid_syntax",
            path=path,
            message=f"configuration does not match the {CONFIG_API_VERSION_V3} schema",
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


def _tenant_id_diagnostics(document: dict[str, Any]) -> list[ConfigDiagnostic]:
    target = document.get("target")
    if not isinstance(target, dict):
        return []
    tenant_id = target.get("tenantId")
    if normalize_uuid_string(tenant_id) is None:
        return [
            ConfigDiagnostic(
                code="config.invalid_tenant_id",
                path=json_pointer("target", "tenantId"),
                message="target.tenantId must be a valid UUID string",
            )
        ]
    return []


def _business_domain_resources(resources: list[Any]) -> list[tuple[int, dict[str, Any]]]:
    items: list[tuple[int, dict[str, Any]]] = []
    for index, item in enumerate(resources):
        if isinstance(item, dict) and item.get("type") == "businessDomain":
            items.append((index, item))
    return items


def _data_product_resources(resources: list[Any]) -> list[tuple[int, dict[str, Any]]]:
    items: list[tuple[int, dict[str, Any]]] = []
    for index, item in enumerate(resources):
        if isinstance(item, dict) and item.get("type") == "dataProduct":
            items.append((index, item))
    return items


def _business_domain_count_diagnostics(document: dict[str, Any]) -> list[ConfigDiagnostic]:
    resources = document.get("resources")
    if not isinstance(resources, list):
        return []
    business_domains = _business_domain_resources(resources)
    if len(business_domains) <= MAX_BUSINESS_DOMAINS:
        return []
    return [
        ConfigDiagnostic(
            code="config.business_domain_count_exceeded",
            path=json_pointer("resources"),
            message=(
                f"resources must contain at most {MAX_BUSINESS_DOMAINS} Business Domain entries"
            ),
        )
    ]


def _duplicate_business_domain_diagnostics(
    document: dict[str, Any],
) -> list[ConfigDiagnostic]:
    resources = document.get("resources")
    if not isinstance(resources, list):
        return []

    seen_ids: dict[str, int] = {}
    seen_names: dict[str, int] = {}
    diagnostics: list[ConfigDiagnostic] = []

    for index, item in _business_domain_resources(resources):
        resource_id = item.get("id")
        if isinstance(resource_id, str):
            normalized_id = normalize_uuid_string(resource_id)
            if normalized_id is not None:
                if normalized_id in seen_ids:
                    diagnostics.append(
                        ConfigDiagnostic(
                            code="config.duplicate_business_domain_id",
                            path=json_pointer("resources", index, "id"),
                            message=(
                                f"duplicate Business Domain id {normalized_id!r}; "
                                f"first seen at /resources/{seen_ids[normalized_id]}/id"
                            ),
                        )
                    )
                else:
                    seen_ids[normalized_id] = index

        props = item.get("properties")
        if not isinstance(props, dict):
            continue
        name = props.get("name")
        if isinstance(name, str):
            if name in seen_names:
                diagnostics.append(
                    ConfigDiagnostic(
                        code="config.duplicate_business_domain_name",
                        path=json_pointer("resources", index, "properties", "name"),
                        message=(
                            f"duplicate Business Domain name {name!r}; "
                            f"first seen at /resources/{seen_names[name]}/properties/name"
                        ),
                    )
                )
            else:
                seen_names[name] = index

    return diagnostics


def _duplicate_data_product_diagnostics(document: dict[str, Any]) -> list[ConfigDiagnostic]:
    resources = document.get("resources")
    if not isinstance(resources, list):
        return []

    seen_ids: dict[str, int] = {}
    diagnostics: list[ConfigDiagnostic] = []

    for index, item in _data_product_resources(resources):
        resource_id = item.get("id")
        if not isinstance(resource_id, str):
            continue
        normalized_id = normalize_uuid_string(resource_id)
        if normalized_id is None:
            continue
        if normalized_id in seen_ids:
            diagnostics.append(
                ConfigDiagnostic(
                    code="config.duplicate_data_product_id",
                    path=json_pointer("resources", index, "id"),
                    message=(
                        f"duplicate Data Product id {normalized_id!r}; "
                        f"first seen at /resources/{seen_ids[normalized_id]}/id"
                    ),
                )
            )
        else:
            seen_ids[normalized_id] = index

    return diagnostics


def _hierarchy_diagnostics(document: dict[str, Any]) -> list[ConfigDiagnostic]:
    resources = document.get("resources")
    if not isinstance(resources, list):
        return []

    entries: list[tuple[int, str, str | None]] = []
    for index, item in _business_domain_resources(resources):
        resource_id = normalize_uuid_string(item.get("id"))
        if resource_id is None:
            continue
        props = item.get("properties")
        parent_id: str | None = None
        if isinstance(props, dict) and "parentId" in props:
            parent_id = normalize_uuid_string(props.get("parentId"))
        entries.append((index, resource_id, parent_id))

    known_ids = {resource_id for _, resource_id, _ in entries}
    parent_by_id: dict[str, str | None] = {
        resource_id: parent_id for _, resource_id, parent_id in entries
    }

    diagnostics: list[ConfigDiagnostic] = []

    for index, resource_id, parent_id in entries:
        if parent_id is None:
            continue
        if parent_id == resource_id:
            diagnostics.append(
                ConfigDiagnostic(
                    code="config.self_parent",
                    path=json_pointer("resources", index, "properties", "parentId"),
                    message=(f"Business Domain {resource_id!r} cannot be its own parent"),
                )
            )

    for index, resource_id, _ in entries:
        visited: set[str] = set()
        current: str | None = resource_id
        depth = 0
        cycle_detected = False
        while current is not None:
            if current in visited:
                cycle_detected = True
                break
            visited.add(current)
            depth += 1
            parent = parent_by_id.get(current)
            if parent is None:
                break
            if parent not in known_ids:
                break
            current = parent

        if cycle_detected:
            diagnostics.append(
                ConfigDiagnostic(
                    code="config.hierarchy_cycle",
                    path=json_pointer("resources", index, "properties", "parentId"),
                    message=(
                        f"Business Domain hierarchy contains a cycle involving {resource_id!r}"
                    ),
                )
            )
            continue

        if depth > MAX_HIERARCHY_DEPTH:
            diagnostics.append(
                ConfigDiagnostic(
                    code="config.hierarchy_depth_exceeded",
                    path=json_pointer("resources", index, "properties", "parentId"),
                    message=(
                        f"Business Domain hierarchy depth exceeds {MAX_HIERARCHY_DEPTH} levels"
                    ),
                )
            )

    return diagnostics


def _semantic_diagnostics(document: dict[str, Any]) -> list[ConfigDiagnostic]:
    diagnostics: list[ConfigDiagnostic] = []
    diagnostics.extend(_tenant_id_diagnostics(document))
    diagnostics.extend(_business_domain_count_diagnostics(document))
    diagnostics.extend(_duplicate_business_domain_diagnostics(document))
    diagnostics.extend(_duplicate_data_product_diagnostics(document))
    diagnostics.extend(_hierarchy_diagnostics(document))
    return diagnostics


def validate_document_v3(document: dict[str, Any]) -> dict[str, Any]:
    """Validate a raw document against the packaged v3 schema and semantics."""
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
    if "apiVersion" in document and api_version != CONFIG_API_VERSION_V3:
        version_diagnostic = ConfigDiagnostic(
            code="config.unsupported_version",
            path=json_pointer("apiVersion"),
            message=f"unsupported apiVersion; expected {CONFIG_API_VERSION_V3!r}",
        )

    schema = load_v3_schema()
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
            continue
        diagnostics.extend(_map_validation_error(error))

    if not diagnostics:
        diagnostics.extend(_semantic_diagnostics(document))

    diagnostics = _dedupe_diagnostics(diagnostics)
    if diagnostics:
        raise ConfigValidationError(diagnostics)
    return document
