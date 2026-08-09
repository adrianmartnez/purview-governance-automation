"""Normalized governance configuration models."""

from __future__ import annotations

import json
from dataclasses import dataclass

from purview_governance.data_source_endpoint import validate_data_source_endpoint


@dataclass(frozen=True, slots=True)
class TargetConfig:
    endpoint: str


@dataclass(frozen=True, slots=True)
class AuthenticationConfig:
    strategy: str


@dataclass(frozen=True, slots=True)
class DataSourceResourceConfig:
    """Closed desired Data Source resource in purview-governance-config/v1."""

    name: str
    kind: str
    endpoint: str
    collection_reference_name: str

    def __post_init__(self) -> None:
        validated = validate_data_source_endpoint(self.endpoint)
        if validated != self.endpoint:
            object.__setattr__(self, "endpoint", validated)

    def to_document(self) -> dict[str, object]:
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
class GovernanceConfig:
    """Deterministic normalized governance configuration (contract v1)."""

    api_version: str
    target: TargetConfig
    authentication: AuthenticationConfig
    resources: tuple[DataSourceResourceConfig, ...] = ()

    def to_document(self) -> dict[str, object]:
        """Return the canonical document shape used for serialization."""
        return {
            "apiVersion": self.api_version,
            "authentication": {"strategy": self.authentication.strategy},
            "resources": [resource.to_document() for resource in self.resources],
            "target": {"endpoint": self.target.endpoint},
        }


def to_canonical_json(config: GovernanceConfig) -> str:
    """Serialize normalized config to deterministic canonical JSON."""
    return json.dumps(
        config.to_document(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
