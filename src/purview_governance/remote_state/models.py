"""Frozen normalized remote-state models for purview-remote-state/v1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from purview_governance.data_source_endpoint import validate_data_source_endpoint
from purview_governance.remote_state.canonical import (
    compute_material_state_identity,
    dumps_canonical,
)

SUPPORTED_KIND = "AzureStorage"
REMOTE_STATE_API_VERSION = "purview-remote-state/v1"

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
