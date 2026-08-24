"""Deterministic normalization for governance config v3."""

from __future__ import annotations

from typing import Any

from purview_governance.config.diagnostics import (
    ConfigDiagnostic,
    ConfigValidationError,
    json_pointer,
)
from purview_governance.config.models import AuthenticationConfig
from purview_governance.config.models_v3 import (
    CONFIG_API_VERSION_V3,
    UNIFIED_CATALOG_SURFACE,
    BusinessDomainResourceConfig,
    GovernanceConfigV3,
    TargetConfigV3,
    business_domain_resource_sort_key,
)
from purview_governance.uuid_utils import normalize_uuid_string


def _require_uuid(
    raw: object,
    *,
    path: tuple[object, ...],
    field_label: str,
) -> str:
    normalized = normalize_uuid_string(raw)
    if normalized is None:
        raise ConfigValidationError(
            (
                ConfigDiagnostic(
                    code="config.invalid_tenant_id"
                    if "tenantId" in path
                    else "config.invalid_syntax",
                    path=json_pointer(*path),
                    message=f"{field_label} must be a valid UUID string",
                ),
            )
        )
    return normalized


def _normalize_business_domain_resource(
    raw: dict[str, Any],
    *,
    index: int,
) -> BusinessDomainResourceConfig:
    path_base = ("resources", index)
    resource_id = _require_uuid(
        raw.get("id"),
        path=(*path_base, "id"),
        field_label="Business Domain id",
    )

    props = raw.get("properties")
    if not isinstance(props, dict):
        raise ConfigValidationError(
            (
                ConfigDiagnostic(
                    code="config.invalid_syntax",
                    path=json_pointer(*path_base, "properties"),
                    message="properties must be an object",
                ),
            )
        )

    name = props.get("name")
    if not isinstance(name, str) or not name:
        raise ConfigValidationError(
            (
                ConfigDiagnostic(
                    code="config.invalid_syntax",
                    path=json_pointer(*path_base, "properties", "name"),
                    message="name must be a non-empty string",
                ),
            )
        )

    description: str | None = None
    if "description" in props:
        raw_description = props["description"]
        if not isinstance(raw_description, str):
            raise ConfigValidationError(
                (
                    ConfigDiagnostic(
                        code="config.invalid_syntax",
                        path=json_pointer(*path_base, "properties", "description"),
                        message="description must be a string",
                    ),
                )
            )
        description = raw_description

    parent_id: str | None = None
    if "parentId" in props:
        parent_id = _require_uuid(
            props.get("parentId"),
            path=(*path_base, "properties", "parentId"),
            field_label="parentId",
        )

    status = props.get("status")
    if status not in {"DRAFT", "PUBLISHED", "EXPIRED"}:
        raise ConfigValidationError(
            (
                ConfigDiagnostic(
                    code="config.invalid_syntax",
                    path=json_pointer(*path_base, "properties", "status"),
                    message="status must be DRAFT, PUBLISHED, or EXPIRED",
                ),
            )
        )

    domain_type = props.get("type")
    allowed_types = {
        "FunctionalUnit",
        "LineOfBusiness",
        "DataDomain",
        "Regulatory",
        "Project",
    }
    if domain_type not in allowed_types:
        raise ConfigValidationError(
            (
                ConfigDiagnostic(
                    code="config.invalid_syntax",
                    path=json_pointer(*path_base, "properties", "type"),
                    message="type must be a supported Business Domain type",
                ),
            )
        )

    is_restricted: bool | None = None
    if "isRestricted" in props:
        raw_is_restricted = props["isRestricted"]
        if not isinstance(raw_is_restricted, bool):
            raise ConfigValidationError(
                (
                    ConfigDiagnostic(
                        code="config.invalid_syntax",
                        path=json_pointer(*path_base, "properties", "isRestricted"),
                        message="isRestricted must be a boolean",
                    ),
                )
            )
        is_restricted = raw_is_restricted

    return BusinessDomainResourceConfig(
        id=resource_id,
        name=name,
        description=description,
        parent_id=parent_id,
        status=status,  # type: ignore[arg-type]
        domain_type=domain_type,  # type: ignore[arg-type]
        is_restricted=is_restricted,
    )


def _normalize_resource(raw: object, *, index: int) -> BusinessDomainResourceConfig:
    path_base = ("resources", index)
    if not isinstance(raw, dict):
        raise ConfigValidationError(
            (
                ConfigDiagnostic(
                    code="config.invalid_syntax",
                    path=json_pointer(*path_base),
                    message="resource must be an object",
                ),
            )
        )
    resource_type = raw.get("type")
    if resource_type != "businessDomain":
        raise ConfigValidationError(
            (
                ConfigDiagnostic(
                    code="config.unknown_field",
                    path=json_pointer(*path_base, "type"),
                    message="unsupported resource type",
                ),
            )
        )
    return _normalize_business_domain_resource(raw, index=index)


def normalize_document_v3(document: dict[str, Any]) -> GovernanceConfigV3:
    """Build an immutable normalized v3 config from a validated document."""
    target_raw = document.get("target")
    if not isinstance(target_raw, dict):
        raise ConfigValidationError(
            (
                ConfigDiagnostic(
                    code="config.invalid_syntax",
                    path=json_pointer("target"),
                    message="target must be an object",
                ),
            )
        )

    surface = target_raw.get("surface")
    if surface != UNIFIED_CATALOG_SURFACE:
        raise ConfigValidationError(
            (
                ConfigDiagnostic(
                    code="config.unknown_field",
                    path=json_pointer("target", "surface"),
                    message="unsupported target surface",
                ),
            )
        )

    tenant_id = _require_uuid(
        target_raw.get("tenantId"),
        path=("target", "tenantId"),
        field_label="target.tenantId",
    )

    auth_raw = document.get("authentication")
    if not isinstance(auth_raw, dict):
        raise ConfigValidationError(
            (
                ConfigDiagnostic(
                    code="config.invalid_syntax",
                    path=json_pointer("authentication"),
                    message="authentication must be an object",
                ),
            )
        )

    raw_resources = document.get("resources") or ()
    resources = tuple(
        _normalize_resource(item, index=index) for index, item in enumerate(raw_resources)
    )
    resources = tuple(sorted(resources, key=business_domain_resource_sort_key))

    return GovernanceConfigV3(
        api_version=CONFIG_API_VERSION_V3,
        target=TargetConfigV3(surface=UNIFIED_CATALOG_SURFACE, tenant_id=tenant_id),
        authentication=AuthenticationConfig(strategy=str(auth_raw["strategy"])),
        resources=resources,
    )
