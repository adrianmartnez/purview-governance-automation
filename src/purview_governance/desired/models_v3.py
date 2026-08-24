"""Desired-state comparison models for Business Domains and Data Products (contract v3)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from purview_governance.config.models_v3 import (
    AudienceType,
    BusinessDomainStatus,
    BusinessDomainType,
    DataProductType,
    UpdateFrequencyType,
)


@dataclass(frozen=True, slots=True)
class DataProductOwnerDesiredState:
    id: str
    description: str | None = None


@dataclass(frozen=True, slots=True)
class BusinessDomainDesiredState:
    """Material desired fields for a Business Domain (UUID-keyed)."""

    id: str
    name: str
    description: str | None
    parent_id: str | None
    status: BusinessDomainStatus
    domain_type: BusinessDomainType
    is_restricted: bool | None = None

    def to_document(self) -> dict[str, Any]:
        properties: dict[str, Any] = {
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
            "id": self.id,
            "properties": properties,
        }


@dataclass(frozen=True, slots=True)
class DataProductDesiredState:
    """Material desired fields for a Data Product (UUID-keyed)."""

    id: str
    name: str
    domain: str
    product_type: DataProductType
    description: str
    business_use: str
    owners: tuple[DataProductOwnerDesiredState, ...]
    audience: tuple[AudienceType, ...] | None = None
    update_frequency: UpdateFrequencyType | None = None
    endorsed: bool | None = None

    def to_document(self) -> dict[str, Any]:
        properties: dict[str, Any] = {
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
            "id": self.id,
            "properties": properties,
        }


@dataclass(frozen=True, slots=True)
class GlossaryTermOwnerDesiredState:
    id: str
    description: str | None = None


@dataclass(frozen=True, slots=True)
class GlossaryTermDesiredState:
    """Material desired fields for a Glossary Term (UUID-keyed)."""

    id: str
    name: str
    domain: str
    description: str
    owners: tuple[GlossaryTermOwnerDesiredState, ...]
    parent_id: str | None = None  # None = ROOT intent (NOT unmanaged)
    acronyms: tuple[str, ...] | None = None  # None=not owned; ()=explicit clear

    def to_document(self) -> dict[str, Any]:
        properties: dict[str, Any] = {
            "name": self.name,
            "domain": self.domain,
            "description": self.description,
            "owners": [
                {
                    "id": owner.id,
                    **({"description": owner.description} if owner.description is not None else {}),
                }
                for owner in self.owners
            ],
        }
        if self.parent_id is not None:
            properties["parentId"] = self.parent_id
        if self.acronyms is not None:
            properties["acronyms"] = list(self.acronyms)
        return {
            "id": self.id,
            "properties": properties,
        }


@dataclass(frozen=True, slots=True)
class DesiredStateV3:
    """Deterministic desired-state snapshot for Unified Catalog v3."""

    business_domains: tuple[BusinessDomainDesiredState, ...] = ()
    data_products: tuple[DataProductDesiredState, ...] = ()
    glossary_terms: tuple[GlossaryTermDesiredState, ...] = ()

    def to_document(self) -> dict[str, Any]:
        doc: dict[str, Any] = {
            "businessDomains": [item.to_document() for item in self.business_domains],
        }
        if self.data_products:
            doc["dataProducts"] = [item.to_document() for item in self.data_products]
        if self.glossary_terms:
            doc["glossaryTerms"] = [item.to_document() for item in self.glossary_terms]
        return doc
