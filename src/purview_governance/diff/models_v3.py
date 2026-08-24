"""Diff models for Business Domains and Data Products (contract v3)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from purview_governance.diff.models import DiffOutcome, DiffReason


@dataclass(frozen=True, slots=True)
class DiffBusinessDomainItem:
    """Change-set item for a Business Domain (UUID-keyed)."""

    id: str
    resource_type: Literal["businessDomain"]
    outcome: DiffOutcome
    reasons: tuple[DiffReason, ...]

    def to_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.resource_type,
            "outcome": self.outcome,
            "reasons": [reason.to_document() for reason in self.reasons],
        }


@dataclass(frozen=True, slots=True)
class DiffDataProductItem:
    """Change-set item for a Data Product (UUID-keyed)."""

    id: str
    resource_type: Literal["dataProduct"]
    outcome: DiffOutcome
    reasons: tuple[DiffReason, ...]

    def to_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.resource_type,
            "outcome": self.outcome,
            "reasons": [reason.to_document() for reason in self.reasons],
        }
