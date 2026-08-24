"""Read-only Purview Data Source remote-state capture (List + Get)."""

from __future__ import annotations

from typing import Any, Protocol

from jsonschema import Draft202012Validator

from purview_governance.config.models_v3 import UNIFIED_CATALOG_SURFACE
from purview_governance.remote_state.business_domain_normalize import (
    normalize_business_domain,
)
from purview_governance.remote_state.classification_normalize import (
    extract_classification_rule_list_item,
    normalize_custom_classification_rule_get,
)
from purview_governance.remote_state.classification_policy import (
    SUPPORTED_CLASSIFICATION_RULE_KIND,
)
from purview_governance.remote_state.data_asset_normalize import normalize_data_asset
from purview_governance.remote_state.data_column_normalize import normalize_data_column
from purview_governance.remote_state.data_product_normalize import (
    normalize_data_product,
)
from purview_governance.remote_state.data_product_policy import (
    CAPTURED_RESOURCE_TYPE_BUSINESS_DOMAIN,
    CAPTURED_RESOURCE_TYPE_DATA_PRODUCT,
)
from purview_governance.remote_state.errors import RemoteStateError
from purview_governance.remote_state.glossary_term_normalize import (
    normalize_glossary_term,
)
from purview_governance.remote_state.glossary_term_policy import (
    CAPTURED_RESOURCE_TYPE_GLOSSARY_TERM,
)
from purview_governance.remote_state.governance_relationship_normalize import (
    normalize_governance_relationship,
)
from purview_governance.remote_state.models import (
    NormalizedClassificationRule,
    NormalizedDataSource,
    NormalizedScan,
    NormalizedScanRuleSet,
    RemoteState,
    RemoteStateV2,
    UninterpretedClassificationRule,
    UninterpretedDataSource,
    UninterpretedScan,
    UninterpretedScanRuleSet,
    build_remote_state,
    build_remote_state_v2,
)
from purview_governance.remote_state.models_v3 import (
    NormalizedBusinessDomain,
    NormalizedDataAsset,
    NormalizedDataColumn,
    NormalizedDataProduct,
    NormalizedGlossaryTerm,
    NormalizedGovernanceRelationship,
    ReadModelCoverageV3,
    RemoteStateV3,
    RemoteTargetContextV3,
    UninterpretedBusinessDomain,
    UninterpretedDataAsset,
    UninterpretedDataColumn,
    UninterpretedDataProduct,
    UninterpretedGlossaryTerm,
    UninterpretedGovernanceRelationship,
    build_remote_state_v3,
)
from purview_governance.remote_state.normalize import (
    extract_list_item_name,
    normalize_azure_storage_get,
    reject_sensitive_keys,
)
from purview_governance.remote_state.policy import SUPPORTED_KIND
from purview_governance.remote_state.scan_normalize import (
    extract_scan_list_item_name,
    extract_scan_ruleset_list_item_name,
    normalize_azure_storage_msi_scan_get,
    normalize_custom_azure_storage_scan_ruleset_get,
)
from purview_governance.remote_state.scan_policy import (
    SUPPORTED_SCAN_KIND,
    SUPPORTED_SCAN_RULESET_KIND,
    SUPPORTED_SCAN_RULESET_TYPE,
)
from purview_governance.remote_state.schema import (
    load_remote_state_v1_schema,
    load_remote_state_v2_schema,
    load_remote_state_v3_schema,
)
from purview_governance.scanning.client import (
    ClassificationRuleListResult,
    DataSourceListResult,
    ScanListResult,
    ScanRuleSetListResult,
)
from purview_governance.scanning.names import (
    validate_classification_rule_name,
    validate_data_source_name,
    validate_scan_name,
    validate_scan_ruleset_name,
)
from purview_governance.unified_catalog.client import (
    BusinessDomainListResult,
    DataAssetListResult,
    DataColumnQueryResult,
    DataProductListResult,
    GlossaryTermListResult,
    GovernanceRelationshipListResult,
)
from purview_governance.uuid_utils import require_uuid_string


class DataSourceReadClient(Protocol):
    """Minimal read-only seam used by remote-state capture."""

    def list_data_sources(self) -> DataSourceListResult: ...

    def get_data_source(self, name: str) -> dict[str, Any]: ...


class ScanningReadClient(Protocol):
    """Read-only seam for remote-state/v2 capture (DS + CR + Scans + Custom SRS)."""

    def list_data_sources(self) -> DataSourceListResult: ...

    def get_data_source(self, name: str) -> dict[str, Any]: ...

    def list_classification_rules(self) -> ClassificationRuleListResult: ...

    def get_classification_rule(self, name: str) -> dict[str, Any]: ...

    def list_scans(self, data_source_name: str) -> ScanListResult: ...

    def get_scan(self, data_source_name: str, scan_name: str) -> dict[str, Any]: ...

    def list_scan_rule_sets(self) -> ScanRuleSetListResult: ...

    def get_scan_rule_set(self, name: str) -> dict[str, Any]: ...


class UnifiedCatalogReadClient(Protocol):
    """Read-only seam for remote-state/v3 capture (Business Domains enumerate)."""

    @property
    def target_endpoint(self) -> str: ...

    def enumerate_business_domains(self) -> BusinessDomainListResult: ...


class UnifiedCatalogDataProductReadClient(UnifiedCatalogReadClient, Protocol):
    """Read-only seam extending v3 capture with Data Products enumerate."""

    def enumerate_data_products(self) -> DataProductListResult: ...


class UnifiedCatalogGlossaryTermReadClient(UnifiedCatalogReadClient, Protocol):
    """Read-only seam extending v3 capture with Glossary Terms enumerate."""

    def enumerate_glossary_terms(self) -> GlossaryTermListResult: ...


class UnifiedCatalogDataAssetReadClient(UnifiedCatalogReadClient, Protocol):
    """Read-only seam extending v3 capture with Data Assets enumerate."""

    def enumerate_data_assets(self) -> DataAssetListResult: ...


class UnifiedCatalogDataColumnReadClient(UnifiedCatalogReadClient, Protocol):
    """Read-only seam extending v3 capture with Data Column query."""

    def query_data_columns(self) -> DataColumnQueryResult: ...


class UnifiedCatalogGovernanceRelationshipReadClient(UnifiedCatalogReadClient, Protocol):
    """Read-only seam for governance relationship list operations."""

    def list_data_product_relationships(
        self,
        product_id: str,
        *,
        entity_type: str = "DATAASSET",
    ) -> GovernanceRelationshipListResult: ...

    def list_glossary_term_relationships(
        self,
        term_id: str,
        *,
        entity_type: str,
        relationship_type: str = "Related",
    ) -> GovernanceRelationshipListResult: ...


def _collect_data_product_source_ids(
    data_products: tuple[NormalizedDataProduct, ...],
    uninterpreted_data_products: tuple[UninterpretedDataProduct, ...],
) -> tuple[list[str], bool]:
    ids: list[str] = [item.id for item in data_products]
    missing_id = False
    for item in uninterpreted_data_products:
        if item.id is None:
            missing_id = True
        else:
            ids.append(item.id)
    return sorted(set(ids)), missing_id


def _collect_glossary_term_source_ids(
    glossary_terms: tuple[NormalizedGlossaryTerm, ...],
    uninterpreted_glossary_terms: tuple[UninterpretedGlossaryTerm, ...],
) -> tuple[list[str], bool]:
    ids: list[str] = [item.id for item in glossary_terms]
    missing_id = False
    for item in uninterpreted_glossary_terms:
        if item.id is None:
            missing_id = True
        else:
            ids.append(item.id)
    return sorted(set(ids)), missing_id


def _validate_artifact(document: dict[str, Any], *, schema: dict[str, Any]) -> None:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(document), key=lambda e: list(e.absolute_path))
    if errors:
        raise RemoteStateError(
            "remote_state.artifact_serialization_failed",
            "normalized remote-state artifact failed schema validation",
        )


def _capture_data_sources(
    client: DataSourceReadClient,
) -> tuple[list[NormalizedDataSource], list[UninterpretedDataSource]]:
    listed = client.list_data_sources()
    names: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(listed.items):
        name = extract_list_item_name(item, index=index)
        if name in seen:
            raise RemoteStateError(
                "remote_state.duplicate_name",
                "duplicate Data Source name in list results",
                path=f"/value/{index}/name",
            )
        seen.add(name)
        names.append(name)

    names.sort()
    normalized: list[NormalizedDataSource] = []
    uninterpreted: list[UninterpretedDataSource] = []

    for name in names:
        # Re-validate before Get path construction (defense in depth).
        validate_data_source_name(name)
        body = client.get_data_source(name)
        if not isinstance(body, dict):
            raise RemoteStateError(
                "remote_state.invalid_shape",
                "GET response must be a JSON object",
            )
        reject_sensitive_keys(body)

        kind = body.get("kind")
        if kind is None:
            raise RemoteStateError(
                "remote_state.missing_kind",
                "GET response is missing kind",
                path="/kind",
            )
        if not isinstance(kind, str):
            raise RemoteStateError(
                "remote_state.invalid_kind",
                "kind must be a string",
                path="/kind",
            )
        if kind != SUPPORTED_KIND:
            # Account without pretending material normalization.
            # Still verify identity match when name is present.
            remote_name = body.get("name")
            if remote_name is None:
                raise RemoteStateError(
                    "remote_state.identity_mismatch",
                    "GET response is missing name",
                    path="/name",
                )
            if not isinstance(remote_name, str) or remote_name != name:
                raise RemoteStateError(
                    "remote_state.identity_mismatch",
                    "GET response name does not match the requested dataSourceName",
                    path="/name",
                )
            uninterpreted.append(
                UninterpretedDataSource(
                    name=name,
                    kind=kind,
                    reason_code="remote_state.unsupported_kind",
                )
            )
            continue

        normalized.append(normalize_azure_storage_get(body, requested_name=name))

    return normalized, uninterpreted


def capture_remote_state(client: DataSourceReadClient) -> RemoteState:
    """Capture purview-remote-state/v1 via List discovery and authoritative Get.

    Read-only: never calls create-or-replace / PUT / delete.
    """
    normalized, uninterpreted = _capture_data_sources(client)
    state = build_remote_state(tuple(normalized), tuple(uninterpreted))
    try:
        _validate_artifact(state.to_document(), schema=load_remote_state_v1_schema())
    except RemoteStateError:
        raise
    except Exception:
        raise RemoteStateError(
            "remote_state.artifact_serialization_failed",
            "failed to validate remote-state artifact",
        ) from None
    return state


def _capture_classification_rules(
    client: ScanningReadClient,
) -> tuple[list[NormalizedClassificationRule], list[UninterpretedClassificationRule]]:
    listed = client.list_classification_rules()
    custom_names: list[str] = []
    uninterpreted: list[UninterpretedClassificationRule] = []
    seen: set[str] = set()
    for index, item in enumerate(listed.items):
        reject_sensitive_keys(item)
        name, kind = extract_classification_rule_list_item(item, index=index)
        if name in seen:
            raise RemoteStateError(
                "remote_state.duplicate_name",
                "duplicate Classification Rule name in list results",
                path=f"/value/{index}/name",
            )
        seen.add(name)
        if kind != SUPPORTED_CLASSIFICATION_RULE_KIND:
            uninterpreted.append(
                UninterpretedClassificationRule(
                    name=name,
                    kind=kind,
                    reason_code="remote_state.unsupported_kind",
                )
            )
            continue
        custom_names.append(name)

    custom_names.sort()
    normalized: list[NormalizedClassificationRule] = []
    for name in custom_names:
        validate_classification_rule_name(name)
        body = client.get_classification_rule(name)
        if not isinstance(body, dict):
            raise RemoteStateError(
                "remote_state.invalid_shape",
                "GET response must be a JSON object",
            )
        reject_sensitive_keys(body)
        normalized.append(normalize_custom_classification_rule_get(body, requested_name=name))

    return normalized, uninterpreted


def _capture_scans_for_supported_parents(
    client: ScanningReadClient,
    supported_parents: list[NormalizedDataSource],
) -> tuple[list[NormalizedScan], list[UninterpretedScan]]:
    normalized: list[NormalizedScan] = []
    uninterpreted: list[UninterpretedScan] = []

    for parent in supported_parents:
        parent_name = parent.name
        listed = client.list_scans(parent_name)
        scan_names: list[str] = []
        seen: set[str] = set()
        for index, item in enumerate(listed.items):
            scan_name = extract_scan_list_item_name(item, index=index)
            if scan_name in seen:
                raise RemoteStateError(
                    "remote_state.duplicate_name",
                    "duplicate Scan name in list results",
                    path=f"/value/{index}/name",
                )
            seen.add(scan_name)
            scan_names.append(scan_name)

        scan_names.sort()
        for scan_name in scan_names:
            validate_scan_name(scan_name)
            body = client.get_scan(parent_name, scan_name)
            if not isinstance(body, dict):
                raise RemoteStateError(
                    "remote_state.invalid_shape",
                    "GET response must be a JSON object",
                )
            reject_sensitive_keys(body)

            kind = body.get("kind")
            if kind is None:
                raise RemoteStateError(
                    "remote_state.missing_kind",
                    "GET response is missing kind",
                    path="/kind",
                )
            if not isinstance(kind, str):
                raise RemoteStateError(
                    "remote_state.invalid_kind",
                    "kind must be a string",
                    path="/kind",
                )
            if kind != SUPPORTED_SCAN_KIND:
                remote_name = body.get("name")
                if remote_name is None:
                    raise RemoteStateError(
                        "remote_state.identity_mismatch",
                        "GET response is missing name",
                        path="/name",
                    )
                if not isinstance(remote_name, str) or remote_name != scan_name:
                    raise RemoteStateError(
                        "remote_state.identity_mismatch",
                        "GET response name does not match the requested scanName",
                        path="/name",
                    )
                uninterpreted.append(
                    UninterpretedScan(
                        name=scan_name,
                        data_source_name=parent_name,
                        kind=kind,
                        reason_code="remote_state.unsupported_kind",
                    )
                )
                continue

            normalized.append(
                normalize_azure_storage_msi_scan_get(
                    body,
                    requested_data_source_name=parent_name,
                    requested_scan_name=scan_name,
                )
            )

    return normalized, uninterpreted


def _capture_scan_rule_sets(
    client: ScanningReadClient,
) -> tuple[list[NormalizedScanRuleSet], list[UninterpretedScanRuleSet]]:
    listed = client.list_scan_rule_sets()
    names: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(listed.items):
        name = extract_scan_ruleset_list_item_name(item, index=index)
        if name in seen:
            raise RemoteStateError(
                "remote_state.duplicate_name",
                "duplicate Scan Rule Set name in list results",
                path=f"/value/{index}/name",
            )
        seen.add(name)
        names.append(name)

    names.sort()
    normalized: list[NormalizedScanRuleSet] = []
    uninterpreted: list[UninterpretedScanRuleSet] = []

    for name in names:
        validate_scan_ruleset_name(name)
        body = client.get_scan_rule_set(name)
        if not isinstance(body, dict):
            raise RemoteStateError(
                "remote_state.invalid_shape",
                "GET response must be a JSON object",
            )
        reject_sensitive_keys(body)

        kind = body.get("kind")
        if kind is None:
            raise RemoteStateError(
                "remote_state.missing_kind",
                "GET response is missing kind",
                path="/kind",
            )
        if not isinstance(kind, str):
            raise RemoteStateError(
                "remote_state.invalid_kind",
                "kind must be a string",
                path="/kind",
            )

        scan_ruleset_type = body.get("scanRulesetType")
        supported = kind == SUPPORTED_SCAN_RULESET_KIND and (
            scan_ruleset_type is None or scan_ruleset_type == SUPPORTED_SCAN_RULESET_TYPE
        )
        if not supported:
            remote_name = body.get("name")
            if remote_name is None:
                raise RemoteStateError(
                    "remote_state.identity_mismatch",
                    "GET response is missing name",
                    path="/name",
                )
            if not isinstance(remote_name, str) or remote_name != name:
                raise RemoteStateError(
                    "remote_state.identity_mismatch",
                    "GET response name does not match the requested scanRulesetName",
                    path="/name",
                )
            reason = "remote_state.unsupported_kind"
            if (
                kind == SUPPORTED_SCAN_RULESET_KIND
                and scan_ruleset_type is not None
                and scan_ruleset_type != SUPPORTED_SCAN_RULESET_TYPE
            ):
                reason = "remote_state.unsupported_scan_ruleset_type"
            uninterpreted.append(
                UninterpretedScanRuleSet(
                    name=name,
                    kind=kind,
                    reason_code=reason,
                )
            )
            continue

        try:
            normalized.append(
                normalize_custom_azure_storage_scan_ruleset_get(
                    body,
                    requested_name=name,
                )
            )
        except RemoteStateError as exc:
            if exc.code in {
                "remote_state.unsupported_kind",
                "remote_state.unsupported_scan_ruleset_type",
            }:
                uninterpreted.append(
                    UninterpretedScanRuleSet(
                        name=name,
                        kind=kind,
                        reason_code=exc.code,
                    )
                )
                continue
            raise

    return normalized, uninterpreted


def capture_remote_state_v2(client: ScanningReadClient) -> RemoteStateV2:
    """Capture purview-remote-state/v2 (DS + Custom CR + Scans + Custom SRS).

    Read-only: never calls create-or-replace / PUT / delete.
    Scans are listed/gotten only for parents already normalized as AzureStorage.
    System (and other non-Custom) Classification Rules are accounted from LIST
    without GET.
    """
    data_sources, uninterpreted_data_sources = _capture_data_sources(client)
    classification_rules, uninterpreted_classification_rules = _capture_classification_rules(client)
    scans, uninterpreted_scans = _capture_scans_for_supported_parents(
        client,
        data_sources,
    )
    scan_rule_sets, uninterpreted_scan_rule_sets = _capture_scan_rule_sets(client)

    state = build_remote_state_v2(
        tuple(data_sources),
        tuple(uninterpreted_data_sources),
        tuple(classification_rules),
        tuple(uninterpreted_classification_rules),
        tuple(scans),
        tuple(uninterpreted_scans),
        tuple(scan_rule_sets),
        tuple(uninterpreted_scan_rule_sets),
    )
    try:
        _validate_artifact(state.to_document(), schema=load_remote_state_v2_schema())
    except RemoteStateError:
        raise
    except Exception:
        raise RemoteStateError(
            "remote_state.artifact_serialization_failed",
            "failed to validate remote-state artifact",
        ) from None
    return state


def capture_unified_catalog_remote_state_v3(
    client: UnifiedCatalogReadClient,
    *,
    tenant_id: str,
    include_data_products: bool = False,
    include_glossary_terms: bool = False,
    include_data_assets: bool = False,
    include_data_columns: bool = False,
    include_relationship_data_product_to_data_asset: bool = False,
    include_relationship_glossary_term_to_data_asset: bool = False,
    include_relationship_glossary_term_to_data_column: bool = False,
) -> RemoteStateV3:
    """Capture purview-remote-state/v3 via Business Domains enumerate.

    Read-only: never calls create / update / delete.
    ``tenant_id`` is declared target binding (not observed from enumerate).

    When both ``include_data_products`` and ``include_glossary_terms`` are False
    (default), emits Shape A (PR2 compatible): Business Domains only.

    Shape B: ``include_data_products=True`` only.
    Shape C: ``include_glossary_terms=True`` only.
    Shape D: both flags True.
    """
    if include_relationship_data_product_to_data_asset and not include_data_products:
        raise RemoteStateError(
            "remote_state.missing_capability",
            "include_relationship_data_product_to_data_asset requires include_data_products",
        )
    if include_relationship_glossary_term_to_data_asset and not include_glossary_terms:
        raise RemoteStateError(
            "remote_state.missing_capability",
            "include_relationship_glossary_term_to_data_asset requires include_glossary_terms",
        )
    if include_relationship_glossary_term_to_data_column and not include_glossary_terms:
        raise RemoteStateError(
            "remote_state.missing_capability",
            "include_relationship_glossary_term_to_data_column requires include_glossary_terms",
        )

    from purview_governance.plan.identity import compute_target_context_identity_v3

    declared_tenant_id = require_uuid_string(tenant_id, field_label="tenantId")
    endpoint = client.target_endpoint
    target_identity = compute_target_context_identity_v3(
        surface=UNIFIED_CATALOG_SURFACE,
        tenant_id=declared_tenant_id,
        endpoint=endpoint,
    )
    target_context = RemoteTargetContextV3(
        surface=UNIFIED_CATALOG_SURFACE,
        tenant_id=declared_tenant_id,
        endpoint=endpoint,
        identity=target_identity,
    )

    listed = client.enumerate_business_domains()
    normalized: list[NormalizedBusinessDomain] = []
    uninterpreted: list[UninterpretedBusinessDomain] = []

    for index, item in enumerate(listed.items):
        if not isinstance(item, dict):
            raise RemoteStateError(
                "remote_state.invalid_shape",
                "enumerate item must be a JSON object",
                path=f"/value/{index}",
            )
        result = normalize_business_domain(item)
        if isinstance(result, UninterpretedBusinessDomain):
            uninterpreted.append(result)
        else:
            normalized.append(result)

    data_products: tuple[NormalizedDataProduct, ...] = ()
    uninterpreted_data_products: tuple[UninterpretedDataProduct, ...] = ()
    glossary_terms: tuple[NormalizedGlossaryTerm, ...] = ()
    uninterpreted_glossary_terms: tuple[UninterpretedGlossaryTerm, ...] = ()
    captured_resource_types: tuple[str, ...] = ()

    if include_data_products:
        enumerate_data_products = getattr(client, "enumerate_data_products", None)
        if enumerate_data_products is None:
            raise RemoteStateError(
                "remote_state.missing_capability",
                "client must implement enumerate_data_products when include_data_products is True",
            )
        listed_products = enumerate_data_products()
        normalized_products: list[NormalizedDataProduct] = []
        uninterpreted_products: list[UninterpretedDataProduct] = []
        for index, item in enumerate(listed_products.items):
            if not isinstance(item, dict):
                raise RemoteStateError(
                    "remote_state.invalid_shape",
                    "enumerate item must be a JSON object",
                    path=f"/value/{index}",
                )
            result = normalize_data_product(item)
            if isinstance(result, UninterpretedDataProduct):
                uninterpreted_products.append(result)
            else:
                normalized_products.append(result)
        data_products = tuple(normalized_products)
        uninterpreted_data_products = tuple(uninterpreted_products)

    if include_glossary_terms:
        enumerate_glossary_terms = getattr(client, "enumerate_glossary_terms", None)
        if enumerate_glossary_terms is None:
            raise RemoteStateError(
                "remote_state.missing_capability",
                "client must implement enumerate_glossary_terms when "
                "include_glossary_terms is True",
            )
        listed_terms = enumerate_glossary_terms()
        normalized_terms: list[NormalizedGlossaryTerm] = []
        uninterpreted_terms: list[UninterpretedGlossaryTerm] = []
        for index, item in enumerate(listed_terms.items):
            if not isinstance(item, dict):
                raise RemoteStateError(
                    "remote_state.invalid_shape",
                    "enumerate item must be a JSON object",
                    path=f"/value/{index}",
                )
            result = normalize_glossary_term(item)
            if isinstance(result, UninterpretedGlossaryTerm):
                uninterpreted_terms.append(result)
            else:
                normalized_terms.append(result)
        glossary_terms = tuple(normalized_terms)
        uninterpreted_glossary_terms = tuple(uninterpreted_terms)

    if include_data_products or include_glossary_terms:
        marker: list[str] = [CAPTURED_RESOURCE_TYPE_BUSINESS_DOMAIN]
        if include_data_products:
            marker.append(CAPTURED_RESOURCE_TYPE_DATA_PRODUCT)
        if include_glossary_terms:
            marker.append(CAPTURED_RESOURCE_TYPE_GLOSSARY_TERM)
        captured_resource_types = tuple(marker)

        captured_resource_types = tuple(marker)

    data_assets: tuple[NormalizedDataAsset, ...] = ()
    uninterpreted_data_assets: tuple[UninterpretedDataAsset, ...] = ()
    data_columns: tuple[NormalizedDataColumn, ...] = ()
    uninterpreted_data_columns: tuple[UninterpretedDataColumn, ...] = ()
    governance_relationships: tuple[NormalizedGovernanceRelationship, ...] = ()
    uninterpreted_governance_relationships: tuple[UninterpretedGovernanceRelationship, ...] = ()
    read_model_coverage: ReadModelCoverageV3 | None = None

    if include_data_assets:
        enumerate_data_assets = getattr(client, "enumerate_data_assets", None)
        if enumerate_data_assets is None:
            raise RemoteStateError(
                "remote_state.missing_capability",
                "client must implement enumerate_data_assets when include_data_assets is True",
            )
        listed_assets = enumerate_data_assets()
        normalized_assets: list[NormalizedDataAsset] = []
        uninterpreted_assets: list[UninterpretedDataAsset] = []
        for index, item in enumerate(listed_assets.items):
            if not isinstance(item, dict):
                raise RemoteStateError(
                    "remote_state.invalid_shape",
                    "enumerate item must be a JSON object",
                    path=f"/value/{index}",
                )
            result = normalize_data_asset(item)
            if isinstance(result, UninterpretedDataAsset):
                uninterpreted_assets.append(result)
            else:
                normalized_assets.append(result)
        data_assets = tuple(normalized_assets)
        uninterpreted_data_assets = tuple(uninterpreted_assets)

    if include_data_columns:
        query_data_columns = getattr(client, "query_data_columns", None)
        if query_data_columns is None:
            raise RemoteStateError(
                "remote_state.missing_capability",
                "client must implement query_data_columns when include_data_columns is True",
            )
        listed_columns = query_data_columns()
        normalized_columns: list[NormalizedDataColumn] = []
        uninterpreted_columns: list[UninterpretedDataColumn] = []
        for index, item in enumerate(listed_columns.items):
            if not isinstance(item, dict):
                raise RemoteStateError(
                    "remote_state.invalid_shape",
                    "query item must be a JSON object",
                    path=f"/value/{index}",
                )
            result = normalize_data_column(item)
            if isinstance(result, UninterpretedDataColumn):
                uninterpreted_columns.append(result)
            else:
                normalized_columns.append(result)
        data_columns = tuple(normalized_columns)
        uninterpreted_data_columns = tuple(uninterpreted_columns)

    relationship_flags = (
        include_relationship_data_product_to_data_asset,
        include_relationship_glossary_term_to_data_asset,
        include_relationship_glossary_term_to_data_column,
    )
    if any(relationship_flags):
        list_dp_rel = getattr(client, "list_data_product_relationships", None)
        list_gt_rel = getattr(client, "list_glossary_term_relationships", None)
        if include_relationship_data_product_to_data_asset and list_dp_rel is None:
            raise RemoteStateError(
                "remote_state.missing_capability",
                "client must implement list_data_product_relationships",
            )
        if (
            include_relationship_glossary_term_to_data_asset
            or include_relationship_glossary_term_to_data_column
        ) and list_gt_rel is None:
            raise RemoteStateError(
                "remote_state.missing_capability",
                "client must implement list_glossary_term_relationships",
            )

        normalized_relationships: list[NormalizedGovernanceRelationship] = []
        uninterpreted_relationships: list[UninterpretedGovernanceRelationship] = []

        if include_relationship_data_product_to_data_asset:
            dp_ids, missing_dp_id = _collect_data_product_source_ids(
                data_products,
                uninterpreted_data_products,
            )
            if missing_dp_id:
                raise RemoteStateError(
                    "remote_state.invalid_shape",
                    "uninterpreted data product without id blocks relationship capture",
                )
            for product_id in dp_ids:
                listed = list_dp_rel(product_id, entity_type="DATAASSET")
                for index, item in enumerate(listed.items):
                    if not isinstance(item, dict):
                        raise RemoteStateError(
                            "remote_state.invalid_shape",
                            "relationship item must be a JSON object",
                            path=f"/value/{index}",
                        )
                    result = normalize_governance_relationship(
                        item,
                        source_type="dataProduct",
                        source_id=product_id,
                        target_category="DATAASSET",
                    )
                    if isinstance(result, UninterpretedGovernanceRelationship):
                        uninterpreted_relationships.append(result)
                    else:
                        normalized_relationships.append(result)

        if (
            include_relationship_glossary_term_to_data_asset
            or include_relationship_glossary_term_to_data_column
        ):
            gt_ids, missing_gt_id = _collect_glossary_term_source_ids(
                glossary_terms,
                uninterpreted_glossary_terms,
            )
            if missing_gt_id:
                raise RemoteStateError(
                    "remote_state.invalid_shape",
                    "uninterpreted glossary term without id blocks relationship capture",
                )
            for term_id in gt_ids:
                if include_relationship_glossary_term_to_data_asset:
                    listed = list_gt_rel(
                        term_id,
                        entity_type="DATAASSET",
                        relationship_type="Related",
                    )
                    for index, item in enumerate(listed.items):
                        if not isinstance(item, dict):
                            raise RemoteStateError(
                                "remote_state.invalid_shape",
                                "relationship item must be a JSON object",
                                path=f"/value/{index}",
                            )
                        result = normalize_governance_relationship(
                            item,
                            source_type="glossaryTerm",
                            source_id=term_id,
                            target_category="DATAASSET",
                        )
                        if isinstance(result, UninterpretedGovernanceRelationship):
                            uninterpreted_relationships.append(result)
                        else:
                            normalized_relationships.append(result)
                if include_relationship_glossary_term_to_data_column:
                    listed = list_gt_rel(
                        term_id,
                        entity_type="DATACOLUMN",
                        relationship_type="Related",
                    )
                    for index, item in enumerate(listed.items):
                        if not isinstance(item, dict):
                            raise RemoteStateError(
                                "remote_state.invalid_shape",
                                "relationship item must be a JSON object",
                                path=f"/value/{index}",
                            )
                        result = normalize_governance_relationship(
                            item,
                            source_type="glossaryTerm",
                            source_id=term_id,
                            target_category="DATACOLUMN",
                        )
                        if isinstance(result, UninterpretedGovernanceRelationship):
                            uninterpreted_relationships.append(result)
                        else:
                            normalized_relationships.append(result)

        governance_relationships = tuple(normalized_relationships)
        uninterpreted_governance_relationships = tuple(uninterpreted_relationships)

    if any(
        (
            include_data_assets,
            include_data_columns,
            include_relationship_data_product_to_data_asset,
            include_relationship_glossary_term_to_data_asset,
            include_relationship_glossary_term_to_data_column,
        )
    ):
        read_model_coverage = ReadModelCoverageV3(
            data_assets=include_data_assets,
            data_columns=include_data_columns,
            relationship_data_product_to_data_asset=include_relationship_data_product_to_data_asset,
            relationship_glossary_term_to_data_asset=include_relationship_glossary_term_to_data_asset,
            relationship_glossary_term_to_data_column=include_relationship_glossary_term_to_data_column,
        )

    state = build_remote_state_v3(
        tuple(normalized),
        tuple(uninterpreted),
        target_context,
        data_products=data_products,
        uninterpreted_data_products=uninterpreted_data_products,
        glossary_terms=glossary_terms,
        uninterpreted_glossary_terms=uninterpreted_glossary_terms,
        captured_resource_types=captured_resource_types,
        data_assets=data_assets,
        uninterpreted_data_assets=uninterpreted_data_assets,
        data_columns=data_columns,
        uninterpreted_data_columns=uninterpreted_data_columns,
        governance_relationships=governance_relationships,
        uninterpreted_governance_relationships=uninterpreted_governance_relationships,
        read_model_coverage=read_model_coverage,
    )
    try:
        _validate_artifact(state.to_document(), schema=load_remote_state_v3_schema())
    except RemoteStateError:
        raise
    except Exception:
        raise RemoteStateError(
            "remote_state.artifact_serialization_failed",
            "failed to validate remote-state artifact",
        ) from None
    return state
