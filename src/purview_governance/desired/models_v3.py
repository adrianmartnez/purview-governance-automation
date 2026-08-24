"""Desired-state comparison models for Business Domains (contract v3)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from purview_governance.config.models_v3 import (
    BusinessDomainStatus,
    BusinessDomainType,
)


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
class DesiredStateV3:
    """Deterministic desired-state snapshot for Business Domains."""

    business_domains: tuple[BusinessDomainDesiredState, ...] = ()

    def to_document(self) -> dict[str, Any]:
        return {
            "businessDomains": [item.to_document() for item in self.business_domains],
        }
