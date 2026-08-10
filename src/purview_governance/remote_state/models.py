"""Frozen normalized remote-state models for purview-remote-state/v1 and /v2."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from purview_governance.data_source_endpoint import validate_data_source_endpoint
from purview_governance.remote_state.canonical import (
    compute_material_state_identity,
    dumps_canonical,
)

SUPPORTED_KIND = "AzureStorage"
REMOTE_STATE_API_VERSION = "purview-remote-state/v1"
REMOTE_STATE_API_VERSION_V2 = "purview-remote-state/v2"

CreationTypeValue = Literal["Manual", "AutoNative", "AutoManaged"]
MovingStateTextual = Literal["Active", "Moving", "Failed"]


@dataclass(frozen=True, slots=True)
class UnknownLegacyMovingState:
    """Wire quirk observed in official Get examples: raw value \"0\" (never Active)."""

    raw: Literal["0"] = "0"

    def to_document(self) -> dict[str, str]:
        return {"kind": "unknownLegacyValue", "raw": self.raw}


@dataclass(frozen=True, slots=True)
class ObservedProperties:
    """Known-but-not-proven-non-material AzureStorage properties (typed)."""

    resource_group: str | None = None
    subscription_id: str | None = None
    location: str | None = None
    resource_name: str | None = None
    resource_id: str | None = None
    data_use_governance: str | None = None
    observed_id: str | None = None

    def to_document(self) -> dict[str, str]:
        doc: dict[str, str] = {}
        if self.resource_group is not None:
            doc["resourceGroup"] = self.resource_group
        if self.subscription_id is not None:
            doc["subscriptionId"] = self.subscription_id
        if self.location is not None:
            doc["location"] = self.location
        if self.resource_name is not None:
            doc["resourceName"] = self.resource_name
        if self.resource_id is not None:
            doc["resourceId"] = self.resource_id
        if self.data_use_governance is not None:
            doc["dataUseGovernance"] = self.data_use_governance
        if self.observed_id is not None:
            doc["id"] = self.observed_id
        return doc


@dataclass(frozen=True, slots=True)
class NormalizedDataSource:
    """Normalized supported AzureStorage remote Data Source (no raw body)."""

    name: str
    kind: Literal["AzureStorage"]
    creation_type: CreationTypeValue
    endpoint: str
    collection_reference_name: str
    collection_moving_state: MovingStateTextual | UnknownLegacyMovingState
    observed: ObservedProperties

    def __post_init__(self) -> None:
        # Enforce project endpoint safety on public model construction.
        validated = validate_data_source_endpoint(self.endpoint)
        if validated != self.endpoint:
            object.__setattr__(self, "endpoint", validated)

    def to_document(self) -> dict[str, Any]:
        moving: str | dict[str, str]
        if isinstance(self.collection_moving_state, UnknownLegacyMovingState):
            moving = self.collection_moving_state.to_document()
        else:
            moving = self.collection_moving_state
        return {
            "type": "dataSource",
            "name": self.name,
            "kind": self.kind,
            "creationType": self.creation_type,
            "properties": {
                "endpoint": self.endpoint,
                "collection": {"referenceName": self.collection_reference_name},
                "dataSourceCollectionMovingState": moving,
            },
            "observedProperties": self.observed.to_document(),
        }


@dataclass(frozen=True, slots=True)
class UninterpretedDataSource:
    """Accounted remote Data Source that cannot be safely normalized as AzureStorage."""

    name: str
    kind: str
    reason_code: str

    def to_document(self) -> dict[str, str]:
        return {
            "name": self.name,
            "kind": self.kind,
            "reasonCode": self.reason_code,
        }


@dataclass(frozen=True, slots=True)
class RemoteState:
    """Versioned purview-remote-state/v1 artifact model."""

    data_sources: tuple[NormalizedDataSource, ...]
    uninterpreted_data_sources: tuple[UninterpretedDataSource, ...]
    material_state_identity: str

    def identity_document(self) -> dict[str, Any]:
        """Document hashed for materialStateIdentity (excludes the identity field)."""
        return {
            "apiVersion": REMOTE_STATE_API_VERSION,
            "dataSources": [item.to_document() for item in self.data_sources],
            "uninterpretedDataSources": [
                item.to_document() for item in self.uninterpreted_data_sources
            ],
        }

    def to_document(self) -> dict[str, Any]:
        doc = self.identity_document()
        doc["materialStateIdentity"] = self.material_state_identity
        return doc

    def to_canonical_json(self) -> str:
        return dumps_canonical(self.to_document())


def build_remote_state(
    data_sources: tuple[NormalizedDataSource, ...],
    uninterpreted_data_sources: tuple[UninterpretedDataSource, ...],
) -> RemoteState:
    """Build RemoteState with deterministic identity from sorted inputs."""
    sorted_ds = tuple(sorted(data_sources, key=lambda item: item.name))
    sorted_ui = tuple(sorted(uninterpreted_data_sources, key=lambda item: item.name))
    provisional = RemoteState(
        data_sources=sorted_ds,
        uninterpreted_data_sources=sorted_ui,
        material_state_identity="",
    )
    identity = compute_material_state_identity(provisional.identity_document())
    return RemoteState(
        data_sources=sorted_ds,
        uninterpreted_data_sources=sorted_ui,
        material_state_identity=identity,
    )


@dataclass(frozen=True, slots=True)
class ScanObservedProperties:
    """Observational Scan identifiers (typed; excluded from desired comparison)."""

    observed_id: str | None = None
    scan_id: str | None = None

    def to_document(self) -> dict[str, str]:
        doc: dict[str, str] = {}
        if self.observed_id is not None:
            doc["id"] = self.observed_id
        if self.scan_id is not None:
            doc["scanId"] = self.scan_id
        return doc


@dataclass(frozen=True, slots=True)
class UnsupportedConfigurableField:
    """Evidence that a known configurable field is present but unsupported."""

    path: str
    value_identity: str  # sha256:<hex>

    def to_document(self) -> dict[str, str]:
        return {"path": self.path, "valueIdentity": self.value_identity}


@dataclass(frozen=True, slots=True)
class NormalizedScan:
    """Normalized supported AzureStorageMsi remote Scan (no raw body)."""

    name: str
    data_source_name: str
    kind: Literal["AzureStorageMsi"]
    creation_type: CreationTypeValue
    scan_ruleset_name: str
    scan_ruleset_type: Literal["System", "Custom"]
    collection_reference_name: str
    unsupported_configurable_fields: tuple[UnsupportedConfigurableField, ...] = ()
    observed: ScanObservedProperties = field(default_factory=ScanObservedProperties)

    def to_document(self) -> dict[str, Any]:
        doc: dict[str, Any] = {
            "type": "scan",
            "name": self.name,
            "dataSourceName": self.data_source_name,
            "kind": self.kind,
            "creationType": self.creation_type,
            "properties": {
                "scanRulesetName": self.scan_ruleset_name,
                "scanRulesetType": self.scan_ruleset_type,
                "collection": {"referenceName": self.collection_reference_name},
            },
            "observedProperties": self.observed.to_document(),
        }
        if self.unsupported_configurable_fields:
            doc["unsupportedConfigurableFields"] = [
                item.to_document()
                for item in sorted(self.unsupported_configurable_fields, key=lambda f: f.path)
            ]
        return doc


@dataclass(frozen=True, slots=True)
class UninterpretedScan:
    """Accounted remote Scan that cannot be safely normalized as AzureStorageMsi."""

    name: str
    data_source_name: str
    kind: str
    reason_code: str

    def to_document(self) -> dict[str, str]:
        return {
            "name": self.name,
            "dataSourceName": self.data_source_name,
            "kind": self.kind,
            "reasonCode": self.reason_code,
        }


@dataclass(frozen=True, slots=True)
class NormalizedScanRuleSet:
    """Normalized Custom AzureStorage remote Scan Rule Set (no raw body)."""

    name: str
    kind: Literal["AzureStorage"]
    scan_ruleset_type: Literal["Custom"]
    file_extensions: tuple[str, ...]
    excluded_system_classifications: tuple[str, ...]
    included_custom_classification_rule_names: tuple[str, ...]
    description: str | None = None
    unsupported_configurable_fields: tuple[UnsupportedConfigurableField, ...] = ()

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
        doc: dict[str, Any] = {
            "type": "scanRuleSet",
            "name": self.name,
            "kind": self.kind,
            "scanRulesetType": self.scan_ruleset_type,
            "properties": properties,
        }
        if self.unsupported_configurable_fields:
            doc["unsupportedConfigurableFields"] = [
                item.to_document()
                for item in sorted(self.unsupported_configurable_fields, key=lambda f: f.path)
            ]
        return doc


@dataclass(frozen=True, slots=True)
class UninterpretedScanRuleSet:
    """Accounted remote Scan Rule Set that cannot be safely normalized."""

    name: str
    kind: str
    reason_code: str

    def to_document(self) -> dict[str, str]:
        return {
            "name": self.name,
            "kind": self.kind,
            "reasonCode": self.reason_code,
        }


@dataclass(frozen=True, slots=True)
class RemoteStateV2:
    """Versioned purview-remote-state/v2 artifact model."""

    data_sources: tuple[NormalizedDataSource, ...]
    uninterpreted_data_sources: tuple[UninterpretedDataSource, ...]
    scans: tuple[NormalizedScan, ...]
    uninterpreted_scans: tuple[UninterpretedScan, ...]
    scan_rule_sets: tuple[NormalizedScanRuleSet, ...]
    uninterpreted_scan_rule_sets: tuple[UninterpretedScanRuleSet, ...]
    material_state_identity: str

    def identity_document(self) -> dict[str, Any]:
        """Document hashed for materialStateIdentity (excludes the identity field)."""
        return {
            "apiVersion": REMOTE_STATE_API_VERSION_V2,
            "dataSources": [item.to_document() for item in self.data_sources],
            "uninterpretedDataSources": [
                item.to_document() for item in self.uninterpreted_data_sources
            ],
            "scans": [item.to_document() for item in self.scans],
            "uninterpretedScans": [item.to_document() for item in self.uninterpreted_scans],
            "scanRuleSets": [item.to_document() for item in self.scan_rule_sets],
            "uninterpretedScanRuleSets": [
                item.to_document() for item in self.uninterpreted_scan_rule_sets
            ],
        }

    def to_document(self) -> dict[str, Any]:
        doc = self.identity_document()
        doc["materialStateIdentity"] = self.material_state_identity
        return doc

    def to_canonical_json(self) -> str:
        return dumps_canonical(self.to_document())


def build_remote_state_v2(
    data_sources: tuple[NormalizedDataSource, ...],
    uninterpreted_data_sources: tuple[UninterpretedDataSource, ...],
    scans: tuple[NormalizedScan, ...],
    uninterpreted_scans: tuple[UninterpretedScan, ...],
    scan_rule_sets: tuple[NormalizedScanRuleSet, ...],
    uninterpreted_scan_rule_sets: tuple[UninterpretedScanRuleSet, ...],
) -> RemoteStateV2:
    """Build RemoteStateV2 with deterministic identity from sorted inputs."""
    sorted_ds = tuple(sorted(data_sources, key=lambda item: item.name))
    sorted_ui = tuple(sorted(uninterpreted_data_sources, key=lambda item: item.name))
    sorted_scans = tuple(sorted(scans, key=lambda item: (item.data_source_name, item.name)))
    sorted_ui_scans = tuple(
        sorted(uninterpreted_scans, key=lambda item: (item.data_source_name, item.name))
    )
    sorted_srs = tuple(sorted(scan_rule_sets, key=lambda item: item.name))
    sorted_ui_srs = tuple(sorted(uninterpreted_scan_rule_sets, key=lambda item: item.name))
    provisional = RemoteStateV2(
        data_sources=sorted_ds,
        uninterpreted_data_sources=sorted_ui,
        scans=sorted_scans,
        uninterpreted_scans=sorted_ui_scans,
        scan_rule_sets=sorted_srs,
        uninterpreted_scan_rule_sets=sorted_ui_srs,
        material_state_identity="",
    )
    identity = compute_material_state_identity(provisional.identity_document())
    return RemoteStateV2(
        data_sources=sorted_ds,
        uninterpreted_data_sources=sorted_ui,
        scans=sorted_scans,
        uninterpreted_scans=sorted_ui_scans,
        scan_rule_sets=sorted_srs,
        uninterpreted_scan_rule_sets=sorted_ui_srs,
        material_state_identity=identity,
    )
