"""Frozen normalized remote-state models for purview-remote-state/v3."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from purview_governance.remote_state.canonical import (
    compute_material_state_identity,
    dumps_canonical,
)
from purview_governance.remote_state.data_product_policy import (
    CAPTURED_RESOURCE_TYPE_DATA_PRODUCT,
)
from purview_governance.remote_state.errors import RemoteStateError
from purview_governance.remote_state.glossary_term_policy import (
    CAPTURED_RESOURCE_TYPE_GLOSSARY_TERM,
    VALID_CAPTURE_MARKERS,
)
from purview_governance.remote_state.models import UnsupportedConfigurableField
from purview_governance.remote_state.read_model_coverage_policy import (
    READ_MODEL_COVERAGE_DATA_ASSETS,
    READ_MODEL_COVERAGE_DATA_COLUMNS,
    READ_MODEL_COVERAGE_GOVERNANCE_RELATIONSHIPS,
    RELATIONSHIP_FAMILY_DATA_PRODUCT_TO_DATA_ASSET,
    RELATIONSHIP_FAMILY_GLOSSARY_TERM_TO_DATA_ASSET,
    RELATIONSHIP_FAMILY_GLOSSARY_TERM_TO_DATA_COLUMN,
)

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
class NormalizedGlossaryTerm:
    """Normalized supported Glossary Term (no raw body)."""

    id: str
    properties: dict[str, Any]
    safety_properties: dict[str, Any]
    unsupported_configurable_fields: tuple[UnsupportedConfigurableField, ...] = ()

    def to_document(self) -> dict[str, Any]:
        doc: dict[str, Any] = {
            "type": "glossaryTerm",
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
class UninterpretedGlossaryTerm:
    """Accounted Glossary Term that cannot be safely normalized."""

    reason_code: str
    id: str | None = None

    def to_document(self) -> dict[str, Any]:
        doc: dict[str, Any] = {"reasonCode": self.reason_code}
        if self.id is not None:
            doc["id"] = self.id
        return doc


@dataclass(frozen=True, slots=True)
class NormalizedDataAsset:
    """Normalized supported Data Asset (no raw body)."""

    id: str
    fields: dict[str, Any]
    safety_properties: dict[str, Any] = field(default_factory=dict)

    def to_document(self) -> dict[str, Any]:
        doc: dict[str, Any] = {
            "type": "dataAsset",
            "id": self.id,
            **dict(self.fields),
        }
        if self.safety_properties:
            doc["safetyProperties"] = dict(self.safety_properties)
        return doc


@dataclass(frozen=True, slots=True)
class UninterpretedDataAsset:
    """Accounted Data Asset that cannot be safely normalized."""

    reason_code: str
    id: str | None = None

    def to_document(self) -> dict[str, Any]:
        doc: dict[str, Any] = {"reasonCode": self.reason_code}
        if self.id is not None:
            doc["id"] = self.id
        return doc


@dataclass(frozen=True, slots=True)
class NormalizedDataColumn:
    """Normalized supported Data Column (no raw body)."""

    id: str
    fields: dict[str, Any]

    def to_document(self) -> dict[str, Any]:
        return {
            "type": "dataColumn",
            "id": self.id,
            **dict(self.fields),
        }


@dataclass(frozen=True, slots=True)
class UninterpretedDataColumn:
    """Accounted Data Column that cannot be safely normalized."""

    reason_code: str
    id: str | None = None

    def to_document(self) -> dict[str, Any]:
        doc: dict[str, Any] = {"reasonCode": self.reason_code}
        if self.id is not None:
            doc["id"] = self.id
        return doc


@dataclass(frozen=True, slots=True)
class NormalizedGovernanceRelationship:
    """Normalized supported governance relationship edge (no raw body)."""

    source_type: str
    source_id: str
    target_category: str
    target_id: str
    relationship_type: str
    fields: dict[str, Any] = field(default_factory=dict)

    def identity_key(self) -> tuple[str, str, str, str, str]:
        return (
            self.source_type,
            self.source_id,
            self.target_category,
            self.target_id,
            self.relationship_type,
        )

    def to_document(self) -> dict[str, Any]:
        doc: dict[str, Any] = {
            "type": "governanceRelationship",
            "sourceType": self.source_type,
            "sourceId": self.source_id,
            "targetCategory": self.target_category,
            "targetId": self.target_id,
            "relationshipType": self.relationship_type,
        }
        if self.fields:
            doc.update(dict(self.fields))
        return doc


@dataclass(frozen=True, slots=True)
class UninterpretedGovernanceRelationship:
    """Accounted governance relationship that cannot be safely normalized."""

    reason_code: str
    source_type: str
    source_id: str
    target_category: str
    target_id: str | None = None
    relationship_type: str | None = None

    def to_document(self) -> dict[str, Any]:
        doc: dict[str, Any] = {
            "reasonCode": self.reason_code,
            "sourceType": self.source_type,
            "sourceId": self.source_id,
            "targetCategory": self.target_category,
        }
        if self.target_id is not None:
            doc["targetId"] = self.target_id
        if self.relationship_type is not None:
            doc["relationshipType"] = self.relationship_type
        return doc


@dataclass(frozen=True, slots=True)
class ReadModelCoverageV3:
    """Sparse positive-only read-model coverage markers for PR5 extensions."""

    data_assets: bool = False
    data_columns: bool = False
    relationship_data_product_to_data_asset: bool = False
    relationship_glossary_term_to_data_asset: bool = False
    relationship_glossary_term_to_data_column: bool = False

    @property
    def includes_governance_relationships(self) -> bool:
        return (
            self.relationship_data_product_to_data_asset
            or self.relationship_glossary_term_to_data_asset
            or self.relationship_glossary_term_to_data_column
        )

    def to_document(self) -> dict[str, Any]:
        doc: dict[str, Any] = {}
        if self.data_assets:
            doc[READ_MODEL_COVERAGE_DATA_ASSETS] = True
        if self.data_columns:
            doc[READ_MODEL_COVERAGE_DATA_COLUMNS] = True
        relationship_doc: dict[str, bool] = {}
        if self.relationship_data_product_to_data_asset:
            relationship_doc[RELATIONSHIP_FAMILY_DATA_PRODUCT_TO_DATA_ASSET] = True
        if self.relationship_glossary_term_to_data_asset:
            relationship_doc[RELATIONSHIP_FAMILY_GLOSSARY_TERM_TO_DATA_ASSET] = True
        if self.relationship_glossary_term_to_data_column:
            relationship_doc[RELATIONSHIP_FAMILY_GLOSSARY_TERM_TO_DATA_COLUMN] = True
        if relationship_doc:
            doc[READ_MODEL_COVERAGE_GOVERNANCE_RELATIONSHIPS] = relationship_doc
        if not doc:
            raise RemoteStateError(
                "remote_state.invalid_coverage",
                "readModelCoverage must not be empty when present",
            )
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
    glossary_terms: tuple[NormalizedGlossaryTerm, ...] = ()
    uninterpreted_glossary_terms: tuple[UninterpretedGlossaryTerm, ...] = ()
    captured_resource_types: tuple[str, ...] = ()
    data_assets: tuple[NormalizedDataAsset, ...] = ()
    uninterpreted_data_assets: tuple[UninterpretedDataAsset, ...] = ()
    data_columns: tuple[NormalizedDataColumn, ...] = ()
    uninterpreted_data_columns: tuple[UninterpretedDataColumn, ...] = ()
    governance_relationships: tuple[NormalizedGovernanceRelationship, ...] = ()
    uninterpreted_governance_relationships: tuple[UninterpretedGovernanceRelationship, ...] = ()
    read_model_coverage: ReadModelCoverageV3 | None = None

    @property
    def includes_data_product_capture(self) -> bool:
        return CAPTURED_RESOURCE_TYPE_DATA_PRODUCT in self.captured_resource_types

    @property
    def includes_glossary_term_capture(self) -> bool:
        return CAPTURED_RESOURCE_TYPE_GLOSSARY_TERM in self.captured_resource_types

    @property
    def includes_data_asset_capture(self) -> bool:
        return self.read_model_coverage is not None and self.read_model_coverage.data_assets

    @property
    def includes_data_column_capture(self) -> bool:
        return self.read_model_coverage is not None and self.read_model_coverage.data_columns

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
        if self.captured_resource_types:
            doc["capturedResourceTypes"] = list(self.captured_resource_types)
            if self.includes_data_product_capture:
                doc["dataProducts"] = [item.to_document() for item in self.data_products]
                doc["uninterpretedDataProducts"] = [
                    item.to_document() for item in self.uninterpreted_data_products
                ]
            if self.includes_glossary_term_capture:
                doc["glossaryTerms"] = [item.to_document() for item in self.glossary_terms]
                doc["uninterpretedGlossaryTerms"] = [
                    item.to_document() for item in self.uninterpreted_glossary_terms
                ]
        if self.read_model_coverage is not None:
            doc["readModelCoverage"] = self.read_model_coverage.to_document()
            if self.includes_data_asset_capture:
                doc["dataAssets"] = [item.to_document() for item in self.data_assets]
                doc["uninterpretedDataAssets"] = [
                    item.to_document() for item in self.uninterpreted_data_assets
                ]
            if self.includes_data_column_capture:
                doc["dataColumns"] = [item.to_document() for item in self.data_columns]
                doc["uninterpretedDataColumns"] = [
                    item.to_document() for item in self.uninterpreted_data_columns
                ]
            if self.read_model_coverage.includes_governance_relationships:
                doc["governanceRelationships"] = [
                    item.to_document() for item in self.governance_relationships
                ]
                doc["uninterpretedGovernanceRelationships"] = [
                    item.to_document() for item in self.uninterpreted_governance_relationships
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
    glossary_terms: tuple[NormalizedGlossaryTerm, ...] = (),
    uninterpreted_glossary_terms: tuple[UninterpretedGlossaryTerm, ...] = (),
    captured_resource_types: tuple[str, ...] = (),
    data_assets: tuple[NormalizedDataAsset, ...] = (),
    uninterpreted_data_assets: tuple[UninterpretedDataAsset, ...] = (),
    data_columns: tuple[NormalizedDataColumn, ...] = (),
    uninterpreted_data_columns: tuple[UninterpretedDataColumn, ...] = (),
    governance_relationships: tuple[NormalizedGovernanceRelationship, ...] = (),
    uninterpreted_governance_relationships: tuple[UninterpretedGovernanceRelationship, ...] = (),
    read_model_coverage: ReadModelCoverageV3 | None = None,
) -> RemoteStateV3:
    """Build RemoteStateV3 with deterministic identity from sorted inputs."""
    if captured_resource_types and captured_resource_types not in VALID_CAPTURE_MARKERS:
        raise RemoteStateError(
            "remote_state.invalid_capture_marker",
            "capturedResourceTypes is not a supported capture marker",
        )

    if read_model_coverage is None:
        if any(
            (
                data_assets,
                uninterpreted_data_assets,
                data_columns,
                uninterpreted_data_columns,
                governance_relationships,
                uninterpreted_governance_relationships,
            )
        ):
            raise RemoteStateError(
                "remote_state.invalid_coverage",
                "read-model arrays require readModelCoverage",
            )
    else:
        if read_model_coverage.data_assets is False and (data_assets or uninterpreted_data_assets):
            raise RemoteStateError(
                "remote_state.invalid_coverage",
                "data asset arrays require readModelCoverage.dataAssets",
            )
        if read_model_coverage.data_columns is False and (
            data_columns or uninterpreted_data_columns
        ):
            raise RemoteStateError(
                "remote_state.invalid_coverage",
                "data column arrays require readModelCoverage.dataColumns",
            )
        if read_model_coverage.includes_governance_relationships is False and (
            governance_relationships or uninterpreted_governance_relationships
        ):
            raise RemoteStateError(
                "remote_state.invalid_coverage",
                "governance relationship arrays require readModelCoverage",
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

    seen_gt: set[str] = set()
    for item in glossary_terms:
        if item.id in seen_gt:
            raise RemoteStateError(
                "remote_state.duplicate_id",
                "duplicate Glossary Term id in remote-state inputs",
                path=f"/glossaryTerms/{item.id}",
            )
        seen_gt.add(item.id)
    for item in uninterpreted_glossary_terms:
        if item.id is None:
            continue
        if item.id in seen_gt:
            raise RemoteStateError(
                "remote_state.duplicate_id",
                "duplicate Glossary Term id in remote-state inputs",
                path=f"/uninterpretedGlossaryTerms/{item.id}",
            )
        seen_gt.add(item.id)

    seen_da: set[str] = set()
    for item in data_assets:
        if item.id in seen_da:
            raise RemoteStateError(
                "remote_state.duplicate_id",
                "duplicate Data Asset id in remote-state inputs",
                path=f"/dataAssets/{item.id}",
            )
        seen_da.add(item.id)
    for item in uninterpreted_data_assets:
        if item.id is None:
            continue
        if item.id in seen_da:
            raise RemoteStateError(
                "remote_state.duplicate_id",
                "duplicate Data Asset id in remote-state inputs",
                path=f"/uninterpretedDataAssets/{item.id}",
            )
        seen_da.add(item.id)

    seen_dc: set[str] = set()
    for item in data_columns:
        if item.id in seen_dc:
            raise RemoteStateError(
                "remote_state.duplicate_id",
                "duplicate Data Column id in remote-state inputs",
                path=f"/dataColumns/{item.id}",
            )
        seen_dc.add(item.id)
    for item in uninterpreted_data_columns:
        if item.id is None:
            continue
        if item.id in seen_dc:
            raise RemoteStateError(
                "remote_state.duplicate_id",
                "duplicate Data Column id in remote-state inputs",
                path=f"/uninterpretedDataColumns/{item.id}",
            )
        seen_dc.add(item.id)

    seen_edges: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    for item in governance_relationships:
        key = item.identity_key()
        doc = item.to_document()
        if key in seen_edges:
            if seen_edges[key] != doc:
                raise RemoteStateError(
                    "remote_state.duplicate_id",
                    "divergent governance relationship for the same edge identity",
                )
            raise RemoteStateError(
                "remote_state.duplicate_id",
                "duplicate governance relationship edge identity",
            )
        seen_edges[key] = doc

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
    sorted_terms = tuple(sorted(glossary_terms, key=lambda item: item.id))
    sorted_uninterpreted_gt = tuple(
        sorted(
            uninterpreted_glossary_terms,
            key=lambda item: (item.id is None, item.id or ""),
        )
    )
    sorted_assets = tuple(sorted(data_assets, key=lambda item: item.id))
    sorted_uninterpreted_da = tuple(
        sorted(
            uninterpreted_data_assets,
            key=lambda item: (item.id is None, item.id or ""),
        )
    )
    sorted_columns = tuple(sorted(data_columns, key=lambda item: item.id))
    sorted_uninterpreted_dc = tuple(
        sorted(
            uninterpreted_data_columns,
            key=lambda item: (item.id is None, item.id or ""),
        )
    )
    sorted_relationships = tuple(
        sorted(
            governance_relationships,
            key=lambda item: item.identity_key(),
        )
    )
    sorted_uninterpreted_gr = tuple(
        sorted(
            uninterpreted_governance_relationships,
            key=lambda item: (
                item.source_type,
                item.source_id,
                item.target_category,
                item.target_id or "",
                item.relationship_type or "",
                item.reason_code,
            ),
        )
    )
    sorted_captured = captured_resource_types

    provisional = RemoteStateV3(
        business_domains=sorted_domains,
        uninterpreted_business_domains=sorted_uninterpreted_bd,
        target_context=target_context,
        material_state_identity="",
        data_products=sorted_products,
        uninterpreted_data_products=sorted_uninterpreted_dp,
        glossary_terms=sorted_terms,
        uninterpreted_glossary_terms=sorted_uninterpreted_gt,
        captured_resource_types=sorted_captured,
        data_assets=sorted_assets,
        uninterpreted_data_assets=sorted_uninterpreted_da,
        data_columns=sorted_columns,
        uninterpreted_data_columns=sorted_uninterpreted_dc,
        governance_relationships=sorted_relationships,
        uninterpreted_governance_relationships=sorted_uninterpreted_gr,
        read_model_coverage=read_model_coverage,
    )
    identity = compute_material_state_identity(provisional.identity_document())
    return RemoteStateV3(
        business_domains=sorted_domains,
        uninterpreted_business_domains=sorted_uninterpreted_bd,
        target_context=target_context,
        material_state_identity=identity,
        data_products=sorted_products,
        uninterpreted_data_products=sorted_uninterpreted_dp,
        glossary_terms=sorted_terms,
        uninterpreted_glossary_terms=sorted_uninterpreted_gt,
        captured_resource_types=sorted_captured,
        data_assets=sorted_assets,
        uninterpreted_data_assets=sorted_uninterpreted_da,
        data_columns=sorted_columns,
        uninterpreted_data_columns=sorted_uninterpreted_dc,
        governance_relationships=sorted_relationships,
        uninterpreted_governance_relationships=sorted_uninterpreted_gr,
        read_model_coverage=read_model_coverage,
    )


def remote_observed_count_v3(state: RemoteStateV3) -> int:
    """Count normalized plus uninterpreted Business Domains in a v3 snapshot."""
    return len(state.business_domains) + len(state.uninterpreted_business_domains)
