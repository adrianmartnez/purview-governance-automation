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

DataProductType = Literal[
    "Master",
    "Reference",
    "Analytical",
    "AI",
    "MasterDataAndReferenceData",
    "BusinessSystemOrApplication",
    "ModelTypes",
    "DashboardsOrReports",
    "Operational",
    "MLAITrainingDataSet",
    "MLAITestingDataSet",
    "TransactionalDataset",
    "AnalyticsModel",
    "SemanticModel",
]

AudienceType = Literal[
    "DataEngineer",
    "BIEngineer",
    "DataAnalyst",
    "DataScientist",
    "BusinessAnalyst",
    "SoftwareEngineer",
    "BusinessUser",
    "Executive",
]

UpdateFrequencyType = Literal[
    "Hourly",
    "Daily",
    "Weekly",
    "Monthly",
    "Quarterly",
    "Yearly",
]

DATA_PRODUCT_TYPES: frozenset[str] = frozenset(
    {
        "Master",
        "Reference",
        "Analytical",
        "AI",
        "MasterDataAndReferenceData",
        "BusinessSystemOrApplication",
        "ModelTypes",
        "DashboardsOrReports",
        "Operational",
        "MLAITrainingDataSet",
        "MLAITestingDataSet",
        "TransactionalDataset",
        "AnalyticsModel",
        "SemanticModel",
    },
)


@dataclass(frozen=True, slots=True)
class TargetConfigV3:
    """Unified Catalog target binding (surface + tenant UUID)."""

    surface: str
    tenant_id: str


@dataclass(frozen=True, slots=True)
class DataProductOwnerConfig:
    id: str
    description: str | None = None


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


@dataclass(frozen=True, slots=True)
class DataProductResourceConfig:
    """Desired Data Product resource (config/v3)."""

    id: str
    name: str
    domain: str
    product_type: DataProductType
    description: str
    business_use: str
    owners: tuple[DataProductOwnerConfig, ...]
    audience: tuple[AudienceType, ...] | None = None
    update_frequency: UpdateFrequencyType | None = None
    endorsed: bool | None = None

    @property
    def resource_type(self) -> Literal["dataProduct"]:
        return "dataProduct"

    def to_document(self) -> dict[str, object]:
        properties: dict[str, object] = {
            "name": self.name,
            "domain": self.domain,
            "type": self.product_type,
            "description": self.description,
            "businessUse": self.business_use,
            "owners": [
                {
                    "id": owner.id,
                    **({"description": owner.description} if owner.description is not None else {}),
                }
                for owner in self.owners
            ],
        }
        if self.audience is not None:
            properties["audience"] = list(self.audience)
        if self.update_frequency is not None:
            properties["updateFrequency"] = self.update_frequency
        if self.endorsed is not None:
            properties["endorsed"] = self.endorsed
        return {
            "type": "dataProduct",
            "id": self.id,
            "properties": properties,
        }


ResourceConfigV3 = BusinessDomainResourceConfig | DataProductResourceConfig


def business_domain_resource_sort_key(resource: BusinessDomainResourceConfig) -> tuple[int, str]:
    return (0, resource.id)


def data_product_resource_sort_key(resource: DataProductResourceConfig) -> tuple[int, str]:
    return (1, resource.id)


def resource_sort_key(resource: ResourceConfigV3) -> tuple[int, str]:
    if isinstance(resource, BusinessDomainResourceConfig):
        return business_domain_resource_sort_key(resource)
    return data_product_resource_sort_key(resource)


@dataclass(frozen=True, slots=True)
class GovernanceConfigV3:
    """Deterministic normalized governance configuration (contract v3)."""

    api_version: str
    target: TargetConfigV3
    authentication: AuthenticationConfig
    resources: tuple[ResourceConfigV3, ...] = ()

    def to_document(self) -> dict[str, object]:
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
        return tuple(
            resource
            for resource in self.resources
            if isinstance(resource, BusinessDomainResourceConfig)
        )

    @property
    def data_products(self) -> tuple[DataProductResourceConfig, ...]:
        return tuple(
            resource
            for resource in self.resources
            if isinstance(resource, DataProductResourceConfig)
        )


def to_canonical_json_v3(config: GovernanceConfigV3) -> str:
    """Serialize normalized v3 config to deterministic canonical JSON."""
    return json.dumps(
        config.to_document(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
