"""Normalized governance configuration models (contract v3)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from purview_governance.config.models import AuthenticationConfig

CONFIG_API_VERSION_V3 = "purview-governance-config/v3"
UNIFIED_CATALOG_SURFACE = "unifiedCatalog"
MAX_BUSINESS_DOMAINS = 200
MAX_HIERARCHY_DEPTH = 5

BusinessDomainStatus = Literal["DRAFT", "PUBLISHED", "EXPIRED"]
BusinessDomainType = Literal[
    "FunctionalUnit",
    "LineOfBusiness",
    "DataDomain",
    "Regulatory",
    "Project",
]


@dataclass(frozen=True, slots=True)
class TargetConfigV3:
    """Unified Catalog target binding (surface + tenant UUID)."""

    surface: str
    tenant_id: str


@dataclass(frozen=True, slots=True)
class BusinessDomainResourceConfig:
    """Desired Business Domain resource (config/v3)."""

    id: str
    name: str
    description: str | None
    parent_id: str | None
    status: BusinessDomainStatus
    domain_type: BusinessDomainType
    is_restricted: bool | None = None

    @property
    def resource_type(self) -> Literal["businessDomain"]:
        return "businessDomain"

    def to_document(self) -> dict[str, object]:
        properties: dict[str, object] = {
            "name": self.name,
            "status": self.status,
            "type": self.domain_type,
        }
        if self.description is not None:
            properties["description"] = self.description
        if self.parent_id is not None:
            properties["parentId"] = self.parent_id
        if self.is_restricted is not None:
            properties["isRestricted"] = self.is_restricted
        return {
            "type": "businessDomain",
            "id": self.id,
            "properties": properties,
        }


def business_domain_resource_sort_key(
    resource: BusinessDomainResourceConfig,
) -> str:
    return resource.id


@dataclass(frozen=True, slots=True)
class GovernanceConfigV3:
    """Deterministic normalized governance configuration (contract v3)."""

    api_version: str
    target: TargetConfigV3
    authentication: AuthenticationConfig
    resources: tuple[BusinessDomainResourceConfig, ...] = ()

    def to_document(self) -> dict[str, object]:
        """Return the canonical document shape used for serialization."""
        return {
            "apiVersion": self.api_version,
            "authentication": {"strategy": self.authentication.strategy},
            "resources": [resource.to_document() for resource in self.resources],
            "target": {
                "surface": self.target.surface,
                "tenantId": self.target.tenant_id,
            },
        }

    @property
    def business_domains(self) -> tuple[BusinessDomainResourceConfig, ...]:
        return self.resources


def to_canonical_json_v3(config: GovernanceConfigV3) -> str:
    """Serialize normalized v3 config to deterministic canonical JSON."""
    return json.dumps(
        config.to_document(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
