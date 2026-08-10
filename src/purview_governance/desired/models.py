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
class ScanRuleSetDesiredState:
    """Material desired fields for a Custom AzureStorage Scan Rule Set."""

    name: str
    kind: Literal["AzureStorage"]
    scan_ruleset_type: Literal["Custom"]
    file_extensions: tuple[str, ...]
    excluded_system_classifications: tuple[str, ...]
    included_custom_classification_rule_names: tuple[str, ...]
    description: str | None = None

    def to_document(self) -> dict[str, Any]:
        properties: dict[str, Any] = {
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
class ScanDesiredState:
    """Material desired fields for an AzureStorageMsi Scan."""

    name: str
    kind: Literal["AzureStorageMsi"]
    data_source_name: str
    scan_ruleset_name: str
    scan_ruleset_type: Literal["System", "Custom"]
    collection_reference_name: str

    def to_document(self) -> dict[str, Any]:
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


@dataclass(frozen=True, slots=True)
class DesiredState:
    """Deterministic desired-state snapshot for supported resources."""

    data_sources: tuple[DataSourceDesiredState, ...]
    scan_rule_sets: tuple[ScanRuleSetDesiredState, ...] = ()
    scans: tuple[ScanDesiredState, ...] = ()

    def to_document(self, *, multi_resource: bool = False) -> dict[str, Any]:
        doc: dict[str, Any] = {
            "dataSources": [item.to_document() for item in self.data_sources],
        }
        if multi_resource:
            doc["scanRuleSets"] = [item.to_document() for item in self.scan_rule_sets]
            doc["scans"] = [item.to_document() for item in self.scans]
        return doc
