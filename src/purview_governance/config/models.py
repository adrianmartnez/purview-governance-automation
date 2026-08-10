"""Normalized governance configuration models."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from purview_governance.data_source_endpoint import validate_data_source_endpoint

CONFIG_API_VERSION_V1 = "purview-governance-config/v1"
CONFIG_API_VERSION_V2 = "purview-governance-config/v2"

ResourceTypeRank = Literal["dataSource", "scanRuleSet", "scan"]
_TYPE_RANK: dict[str, int] = {"dataSource": 0, "scanRuleSet": 1, "scan": 2}


@dataclass(frozen=True, slots=True)
class TargetConfig:
    endpoint: str


@dataclass(frozen=True, slots=True)
class AuthenticationConfig:
    strategy: str


@dataclass(frozen=True, slots=True)
class DataSourceResourceConfig:
    """Closed desired Data Source resource."""

    name: str
    kind: str
    endpoint: str
    collection_reference_name: str

    @property
    def resource_type(self) -> Literal["dataSource"]:
        return "dataSource"

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
class ScanRuleSetResourceConfig:
    """Desired Custom AzureStorage Scan Rule Set (config/v2)."""

    name: str
    kind: Literal["AzureStorage"]
    scan_ruleset_type: Literal["Custom"]
    file_extensions: tuple[str, ...]
    excluded_system_classifications: tuple[str, ...]
    included_custom_classification_rule_names: tuple[str, ...]
    description: str | None = None

    @property
    def resource_type(self) -> Literal["scanRuleSet"]:
        return "scanRuleSet"

    def to_document(self) -> dict[str, object]:
        properties: dict[str, object] = {
            "scanningRule": {"fileExtensions": list(self.file_extensions)},
            "excludedSystemClassifications": list(self.excluded_system_classifications),
            "includedCustomClassificationRuleNames": list(
                self.included_custom_classification_rule_names
            ),
        }
        if self.description is not None:
            properties["description"] = self.description
        return {
            "type": "scanRuleSet",
            "name": self.name,
            "kind": self.kind,
            "scanRulesetType": self.scan_ruleset_type,
            "properties": properties,
        }


@dataclass(frozen=True, slots=True)
class ScanResourceConfig:
    """Desired AzureStorageMsi Scan (config/v2)."""

    name: str
    kind: Literal["AzureStorageMsi"]
    data_source_name: str
    scan_ruleset_name: str
    scan_ruleset_type: Literal["System", "Custom"]
    collection_reference_name: str

    @property
    def resource_type(self) -> Literal["scan"]:
        return "scan"

    def to_document(self) -> dict[str, object]:
        return {
            "type": "scan",
            "name": self.name,
            "kind": self.kind,
            "properties": {
                "dataSourceName": self.data_source_name,
                "scanRulesetName": self.scan_ruleset_name,
                "scanRulesetType": self.scan_ruleset_type,
                "collection": {"referenceName": self.collection_reference_name},
            },
        }


GovernanceResourceConfig = DataSourceResourceConfig | ScanRuleSetResourceConfig | ScanResourceConfig


def resource_sort_key(resource: GovernanceResourceConfig) -> tuple[int, str, str]:
    parent = ""
    if isinstance(resource, ScanResourceConfig):
        parent = resource.data_source_name
    return (_TYPE_RANK[resource.resource_type], parent, resource.name)


@dataclass(frozen=True, slots=True)
class GovernanceConfig:
    """Deterministic normalized governance configuration (contract v1 or v2)."""

    api_version: str
    target: TargetConfig
    authentication: AuthenticationConfig
    resources: tuple[GovernanceResourceConfig, ...] = ()

    def to_document(self) -> dict[str, object]:
        """Return the canonical document shape used for serialization."""
        return {
            "apiVersion": self.api_version,
            "authentication": {"strategy": self.authentication.strategy},
            "resources": [resource.to_document() for resource in self.resources],
            "target": {"endpoint": self.target.endpoint},
        }

    @property
    def data_sources(self) -> tuple[DataSourceResourceConfig, ...]:
        return tuple(r for r in self.resources if isinstance(r, DataSourceResourceConfig))

    @property
    def scan_rule_sets(self) -> tuple[ScanRuleSetResourceConfig, ...]:
        return tuple(r for r in self.resources if isinstance(r, ScanRuleSetResourceConfig))

    @property
    def scans(self) -> tuple[ScanResourceConfig, ...]:
        return tuple(r for r in self.resources if isinstance(r, ScanResourceConfig))


def to_canonical_json(config: GovernanceConfig) -> str:
    """Serialize normalized config to deterministic canonical JSON."""
    return json.dumps(
        config.to_document(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
