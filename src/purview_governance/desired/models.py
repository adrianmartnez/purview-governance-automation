"""Desired-state comparison models (material fields only)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from purview_governance.data_source_endpoint import validate_data_source_endpoint


@dataclass(frozen=True, slots=True)
class DataSourceDesiredState:
    """Material desired fields for an AzureStorage Data Source."""

    name: str
    kind: Literal["AzureStorage"]
    endpoint: str
    collection_reference_name: str

    def __post_init__(self) -> None:
        validated = validate_data_source_endpoint(self.endpoint)
        if validated != self.endpoint:
            object.__setattr__(self, "endpoint", validated)

    def to_document(self) -> dict[str, Any]:
        return {
            "type": "dataSource",
            "name": self.name,
            "kind": self.kind,
            "properties": {
                "endpoint": self.endpoint,
                "collection": {"referenceName": self.collection_reference_name},
            },
        }


@dataclass(frozen=True, slots=True)
class DesiredState:
    """Deterministic desired-state snapshot for supported resources."""

    data_sources: tuple[DataSourceDesiredState, ...]

    def to_document(self) -> dict[str, Any]:
        return {
            "dataSources": [item.to_document() for item in self.data_sources],
        }
