"""Deterministic desired-vs-remote diff models (read-only; no plan/apply)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from purview_governance.remote_state.canonical import dumps_canonical

DiffOutcome = Literal["create", "replace", "no-op", "remote-only", "blocked"]
DiffResourceType = Literal["dataSource", "classificationRule", "scanRuleSet", "scan"]


@dataclass(frozen=True, slots=True)
class DiffReason:
    code: str
    path: str
    before: str | None = None
    after: str | None = None

    def to_document(self) -> dict[str, Any]:
        doc: dict[str, Any] = {"code": self.code, "path": self.path}
        if self.before is not None:
            doc["before"] = self.before
        if self.after is not None:
            doc["after"] = self.after
        return doc


@dataclass(frozen=True, slots=True)
class DiffItem:
    name: str
    resource_type: DiffResourceType
    outcome: DiffOutcome
    reasons: tuple[DiffReason, ...]
    data_source_name: str | None = None

    def to_document(self) -> dict[str, Any]:
        doc: dict[str, Any] = {
            "name": self.name,
            "type": self.resource_type,
            "outcome": self.outcome,
            "reasons": [reason.to_document() for reason in self.reasons],
        }
        if self.resource_type == "scan":
            doc["dataSourceName"] = self.data_source_name
        return doc


@dataclass(frozen=True, slots=True)
class DiffDocument:
    items: tuple[DiffItem, ...]

    def to_document(self) -> dict[str, Any]:
        return {"items": [item.to_document() for item in self.items]}

    def to_canonical_json(self) -> str:
        return dumps_canonical(self.to_document())
