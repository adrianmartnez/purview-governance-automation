"""Frozen normalized remote-state models for purview-remote-state/v3."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from purview_governance.remote_state.canonical import (
    compute_material_state_identity,
    dumps_canonical,
)
from purview_governance.remote_state.data_product_policy import (
    CAPTURED_RESOURCE_TYPE_BUSINESS_DOMAIN,
    CAPTURED_RESOURCE_TYPE_DATA_PRODUCT,
)
from purview_governance.remote_state.errors import RemoteStateError
from purview_governance.remote_state.models import UnsupportedConfigurableField

REMOTE_STATE_API_VERSION_V3 = "purview-remote-state/v3"


@dataclass(frozen=True, slots=True)
class RemoteTargetContextV3:
    """Declared Unified Catalog target context (tenant is declared, not observed)."""

    surface: Literal["unifiedCatalog"]
    tenant_id: str
    endpoint: str
    identity: str

    def to_document(self) -> dict[str, Any]:
        return {
            "surface": self.surface,
            "tenantId": self.tenant_id,
            "endpoint": self.endpoint,
            "identity": self.identity,
        }


@dataclass(frozen=True, slots=True)
class NormalizedBusinessDomain:
    """Normalized supported Business Domain (no raw body)."""

    id: str
    properties: dict[str, Any]
    unsupported_configurable_fields: tuple[UnsupportedConfigurableField, ...] = ()

    def to_document(self) -> dict[str, Any]:
        doc: dict[str, Any] = {
            "type": "businessDomain",
            "id": self.id,
            "properties": dict(self.properties),
        }
        if self.unsupported_configurable_fields:
            doc["unsupportedConfigurableFields"] = [
                item.to_document()
                for item in sorted(self.unsupported_configurable_fields, key=lambda f: f.path)
            ]
        return doc


@dataclass(frozen=True, slots=True)
class UninterpretedBusinessDomain:
    """Accounted Business Domain that cannot be safely normalized."""

    reason_code: str
    id: str | None = None

    def to_document(self) -> dict[str, Any]:
        doc: dict[str, Any] = {"reasonCode": self.reason_code}
        if self.id is not None:
            doc["id"] = self.id
        return doc


@dataclass(frozen=True, slots=True)
class NormalizedDataProduct:
    """Normalized supported Data Product (no raw body)."""

    id: str
    properties: dict[str, Any]
    safety_properties: dict[str, Any]
    unsupported_configurable_fields: tuple[UnsupportedConfigurableField, ...] = ()

    def to_document(self) -> dict[str, Any]:
        doc: dict[str, Any] = {
            "type": "dataProduct",
            "id": self.id,
            "properties": dict(self.properties),
            "safetyProperties": dict(self.safety_properties),
        }
        if self.unsupported_configurable_fields:
            doc["unsupportedConfigurableFields"] = [
                item.to_document()
                for item in sorted(self.unsupported_configurable_fields, key=lambda f: f.path)
            ]
        return doc


@dataclass(frozen=True, slots=True)
class UninterpretedDataProduct:
    """Accounted Data Product that cannot be safely normalized."""

    reason_code: str
    id: str | None = None

    def to_document(self) -> dict[str, Any]:
        doc: dict[str, Any] = {"reasonCode": self.reason_code}
        if self.id is not None:
            doc["id"] = self.id
        return doc


@dataclass(frozen=True, slots=True)
class RemoteStateV3:
    """Versioned purview-remote-state/v3 artifact model."""

    business_domains: tuple[NormalizedBusinessDomain, ...]
    uninterpreted_business_domains: tuple[UninterpretedBusinessDomain, ...]
    target_context: RemoteTargetContextV3
    material_state_identity: str
    data_products: tuple[NormalizedDataProduct, ...] = ()
    uninterpreted_data_products: tuple[UninterpretedDataProduct, ...] = ()
    captured_resource_types: tuple[str, ...] = ()

    @property
    def includes_data_product_capture(self) -> bool:
        return CAPTURED_RESOURCE_TYPE_DATA_PRODUCT in self.captured_resource_types

    def identity_document(self) -> dict[str, Any]:
        """Document hashed for materialStateIdentity (excludes the identity field)."""
        doc: dict[str, Any] = {
            "apiVersion": REMOTE_STATE_API_VERSION_V3,
            "targetContext": self.target_context.to_document(),
            "businessDomains": [item.to_document() for item in self.business_domains],
            "uninterpretedBusinessDomains": [
                item.to_document() for item in self.uninterpreted_business_domains
            ],
        }
        if self.includes_data_product_capture:
            doc["capturedResourceTypes"] = list(self.captured_resource_types)
            doc["dataProducts"] = [item.to_document() for item in self.data_products]
            doc["uninterpretedDataProducts"] = [
                item.to_document() for item in self.uninterpreted_data_products
            ]
        return doc

    def to_document(self) -> dict[str, Any]:
        doc = self.identity_document()
        doc["materialStateIdentity"] = self.material_state_identity
        return doc

    def to_canonical_json(self) -> str:
        return dumps_canonical(self.to_document())


def build_remote_state_v3(
    business_domains: tuple[NormalizedBusinessDomain, ...],
    uninterpreted_business_domains: tuple[UninterpretedBusinessDomain, ...],
    target_context: RemoteTargetContextV3,
    *,
    data_products: tuple[NormalizedDataProduct, ...] = (),
    uninterpreted_data_products: tuple[UninterpretedDataProduct, ...] = (),
    captured_resource_types: tuple[str, ...] = (),
) -> RemoteStateV3:
    """Build RemoteStateV3 with deterministic identity from sorted inputs."""
    if captured_resource_types:
        expected = (
            CAPTURED_RESOURCE_TYPE_BUSINESS_DOMAIN,
            CAPTURED_RESOURCE_TYPE_DATA_PRODUCT,
        )
        if captured_resource_types != expected:
            raise RemoteStateError(
                "remote_state.invalid_capture_marker",
                "capturedResourceTypes must be ['businessDomain', 'dataProduct'] when present",
            )

    seen_bd: set[str] = set()
    for item in business_domains:
        if item.id in seen_bd:
            raise RemoteStateError(
                "remote_state.duplicate_id",
                "duplicate Business Domain id in remote-state inputs",
                path=f"/businessDomains/{item.id}",
            )
        seen_bd.add(item.id)
    for item in uninterpreted_business_domains:
        if item.id is None:
            continue
        if item.id in seen_bd:
            raise RemoteStateError(
                "remote_state.duplicate_id",
                "duplicate Business Domain id in remote-state inputs",
                path=f"/uninterpretedBusinessDomains/{item.id}",
            )
        seen_bd.add(item.id)

    seen_dp: set[str] = set()
    for item in data_products:
        if item.id in seen_dp:
            raise RemoteStateError(
                "remote_state.duplicate_id",
                "duplicate Data Product id in remote-state inputs",
                path=f"/dataProducts/{item.id}",
            )
        seen_dp.add(item.id)
    for item in uninterpreted_data_products:
        if item.id is None:
            continue
        if item.id in seen_dp:
            raise RemoteStateError(
                "remote_state.duplicate_id",
                "duplicate Data Product id in remote-state inputs",
                path=f"/uninterpretedDataProducts/{item.id}",
            )
        seen_dp.add(item.id)

    sorted_domains = tuple(sorted(business_domains, key=lambda item: item.id))
    sorted_uninterpreted_bd = tuple(
        sorted(
            uninterpreted_business_domains,
            key=lambda item: (item.id is None, item.id or ""),
        )
    )
    sorted_products = tuple(sorted(data_products, key=lambda item: item.id))
    sorted_uninterpreted_dp = tuple(
        sorted(
            uninterpreted_data_products,
            key=lambda item: (item.id is None, item.id or ""),
        )
    )
    sorted_captured = tuple(sorted(captured_resource_types))

    provisional = RemoteStateV3(
        business_domains=sorted_domains,
        uninterpreted_business_domains=sorted_uninterpreted_bd,
        target_context=target_context,
        material_state_identity="",
        data_products=sorted_products,
        uninterpreted_data_products=sorted_uninterpreted_dp,
        captured_resource_types=sorted_captured,
    )
    identity = compute_material_state_identity(provisional.identity_document())
    return RemoteStateV3(
        business_domains=sorted_domains,
        uninterpreted_business_domains=sorted_uninterpreted_bd,
        target_context=target_context,
        material_state_identity=identity,
        data_products=sorted_products,
        uninterpreted_data_products=sorted_uninterpreted_dp,
        captured_resource_types=sorted_captured,
    )


def remote_observed_count_v3(state: RemoteStateV3) -> int:
    """Count normalized plus uninterpreted Business Domains in a v3 snapshot."""
    return len(state.business_domains) + len(state.uninterpreted_business_domains)
