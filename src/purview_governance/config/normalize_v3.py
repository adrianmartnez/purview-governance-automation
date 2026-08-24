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
    DATA_PRODUCT_TYPES,
    UNIFIED_CATALOG_SURFACE,
    AudienceType,
    BusinessDomainResourceConfig,
    DataProductOwnerConfig,
    DataProductResourceConfig,
    GovernanceConfigV3,
    ResourceConfigV3,
    TargetConfigV3,
    UpdateFrequencyType,
    resource_sort_key,
)
from purview_governance.uuid_utils import normalize_uuid_string

_AUDIENCE_VALUES = {
    "DataEngineer",
    "BIEngineer",
    "DataAnalyst",
    "DataScientist",
    "BusinessAnalyst",
    "SoftwareEngineer",
    "BusinessUser",
    "Executive",
}
_UPDATE_FREQUENCY_VALUES = {
    "Hourly",
    "Daily",
    "Weekly",
    "Monthly",
    "Quarterly",
    "Yearly",
}


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


def _normalize_owners(
    raw_owners: object,
    *,
    path_base: tuple[object, ...],
) -> tuple[DataProductOwnerConfig, ...]:
    if not isinstance(raw_owners, list) or not raw_owners:
        raise ConfigValidationError(
            (
                ConfigDiagnostic(
                    code="config.invalid_syntax",
                    path=json_pointer(*path_base, "owners"),
                    message="owners must be a non-empty array",
                ),
            )
        )
    owners: list[DataProductOwnerConfig] = []
    seen: set[str] = set()
    for owner_index, entry in enumerate(raw_owners):
        if not isinstance(entry, dict):
            raise ConfigValidationError(
                (
                    ConfigDiagnostic(
                        code="config.invalid_syntax",
                        path=json_pointer(*path_base, "owners", owner_index),
                        message="owner must be an object",
                    ),
                )
            )
        owner_id = _require_uuid(
            entry.get("id"),
            path=(*path_base, "owners", owner_index, "id"),
            field_label="owner id",
        )
        if owner_id in seen:
            raise ConfigValidationError(
                (
                    ConfigDiagnostic(
                        code="config.invalid_syntax",
                        path=json_pointer(*path_base, "owners", owner_index, "id"),
                        message=f"duplicate owner id {owner_id!r}",
                    ),
                )
            )
        seen.add(owner_id)
        description: str | None = None
        if "description" in entry:
            desc = entry["description"]
            if not isinstance(desc, str):
                raise ConfigValidationError(
                    (
                        ConfigDiagnostic(
                            code="config.invalid_syntax",
                            path=json_pointer(*path_base, "owners", owner_index, "description"),
                            message="owner description must be a string",
                        ),
                    )
                )
            description = desc
        owners.append(DataProductOwnerConfig(id=owner_id, description=description))
    owners.sort(key=lambda item: item.id)
    return tuple(owners)


def _normalize_audience(
    raw_audience: object,
    *,
    path_base: tuple[object, ...],
) -> tuple[AudienceType, ...]:
    if not isinstance(raw_audience, list):
        raise ConfigValidationError(
            (
                ConfigDiagnostic(
                    code="config.invalid_syntax",
                    path=json_pointer(*path_base, "audience"),
                    message="audience must be an array",
                ),
            )
        )
    seen: set[str] = set()
    values: list[str] = []
    for index, entry in enumerate(raw_audience):
        if not isinstance(entry, str) or entry not in _AUDIENCE_VALUES:
            raise ConfigValidationError(
                (
                    ConfigDiagnostic(
                        code="config.invalid_syntax",
                        path=json_pointer(*path_base, "audience", index),
                        message="audience entry is not a supported enum value",
                    ),
                )
            )
        if entry in seen:
            raise ConfigValidationError(
                (
                    ConfigDiagnostic(
                        code="config.invalid_syntax",
                        path=json_pointer(*path_base, "audience", index),
                        message=f"duplicate audience value {entry!r}",
                    ),
                )
            )
        seen.add(entry)
        values.append(entry)
    return tuple(sorted(values))  # type: ignore[return-value]


def _normalize_data_product_resource(
    raw: dict[str, Any],
    *,
    index: int,
) -> DataProductResourceConfig:
    path_base = ("resources", index)
    resource_id = _require_uuid(
        raw.get("id"),
        path=(*path_base, "id"),
        field_label="Data Product id",
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

    domain = _require_uuid(
        props.get("domain"),
        path=(*path_base, "properties", "domain"),
        field_label="domain",
    )

    product_type = props.get("type")
    if not isinstance(product_type, str) or product_type not in DATA_PRODUCT_TYPES:
        raise ConfigValidationError(
            (
                ConfigDiagnostic(
                    code="config.invalid_syntax",
                    path=json_pointer(*path_base, "properties", "type"),
                    message="type must be a supported Data Product type",
                ),
            )
        )

    description = props.get("description")
    if not isinstance(description, str) or not description:
        raise ConfigValidationError(
            (
                ConfigDiagnostic(
                    code="config.invalid_syntax",
                    path=json_pointer(*path_base, "properties", "description"),
                    message="description must be a non-empty string",
                ),
            )
        )
    if len(description) > 10_000:
        raise ConfigValidationError(
            (
                ConfigDiagnostic(
                    code="config.invalid_syntax",
                    path=json_pointer(*path_base, "properties", "description"),
                    message="description must not exceed 10000 characters",
                ),
            )
        )

    business_use = props.get("businessUse")
    if not isinstance(business_use, str) or not business_use:
        raise ConfigValidationError(
            (
                ConfigDiagnostic(
                    code="config.invalid_syntax",
                    path=json_pointer(*path_base, "properties", "businessUse"),
                    message="businessUse must be a non-empty string",
                ),
            )
        )

    owners = _normalize_owners(props.get("owners"), path_base=(*path_base, "properties"))

    audience: tuple[AudienceType, ...] | None = None
    if "audience" in props:
        audience = _normalize_audience(props["audience"], path_base=(*path_base, "properties"))

    update_frequency: UpdateFrequencyType | None = None
    if "updateFrequency" in props:
        freq = props["updateFrequency"]
        if not isinstance(freq, str) or freq not in _UPDATE_FREQUENCY_VALUES:
            raise ConfigValidationError(
                (
                    ConfigDiagnostic(
                        code="config.invalid_syntax",
                        path=json_pointer(*path_base, "properties", "updateFrequency"),
                        message="updateFrequency is not a supported enum value",
                    ),
                )
            )
        update_frequency = freq  # type: ignore[assignment]

    endorsed: bool | None = None
    if "endorsed" in props:
        raw_endorsed = props["endorsed"]
        if not isinstance(raw_endorsed, bool):
            raise ConfigValidationError(
                (
                    ConfigDiagnostic(
                        code="config.invalid_syntax",
                        path=json_pointer(*path_base, "properties", "endorsed"),
                        message="endorsed must be a boolean",
                    ),
                )
            )
        endorsed = raw_endorsed

    return DataProductResourceConfig(
        id=resource_id,
        name=name,
        domain=domain,
        product_type=product_type,  # type: ignore[arg-type]
        description=description,
        business_use=business_use,
        owners=owners,
        audience=audience,
        update_frequency=update_frequency,
        endorsed=endorsed,
    )


def _normalize_resource(raw: object, *, index: int) -> ResourceConfigV3:
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
    if resource_type == "businessDomain":
        return _normalize_business_domain_resource(raw, index=index)
    if resource_type == "dataProduct":
        return _normalize_data_product_resource(raw, index=index)
    raise ConfigValidationError(
        (
            ConfigDiagnostic(
                code="config.unknown_field",
                path=json_pointer(*path_base, "type"),
                message="unsupported resource type",
            ),
        )
    )


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
    resources = tuple(sorted(resources, key=resource_sort_key))

    return GovernanceConfigV3(
        api_version=CONFIG_API_VERSION_V3,
        target=TargetConfigV3(surface=UNIFIED_CATALOG_SURFACE, tenant_id=tenant_id),
        authentication=AuthenticationConfig(strategy=str(auth_raw["strategy"])),
        resources=resources,
    )
