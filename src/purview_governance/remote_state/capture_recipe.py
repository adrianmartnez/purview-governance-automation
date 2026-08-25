"""Derive Unified Catalog capture flags from a planned remote-state/v3 artifact."""

from __future__ import annotations

from dataclasses import dataclass

from purview_governance.remote_state.data_product_policy import (
    CAPTURED_RESOURCE_TYPE_DATA_PRODUCT,
)
from purview_governance.remote_state.errors import RemoteStateError
from purview_governance.remote_state.glossary_term_policy import (
    CAPTURED_RESOURCE_TYPE_GLOSSARY_TERM,
)
from purview_governance.remote_state.models_v3 import RemoteStateV3


@dataclass(frozen=True, slots=True)
class UnifiedCatalogCaptureRecipeV3:
    """Exact kwargs replay for ``capture_unified_catalog_remote_state_v3``."""

    include_data_products: bool
    include_glossary_terms: bool
    include_data_assets: bool
    include_data_columns: bool
    include_relationship_data_product_to_data_asset: bool
    include_relationship_glossary_term_to_data_asset: bool
    include_relationship_glossary_term_to_data_column: bool


def derive_capture_recipe(planned_remote: RemoteStateV3) -> UnifiedCatalogCaptureRecipeV3:
    """Replay the capture shape encoded in the planned remote artifact."""
    coverage = planned_remote.read_model_coverage
    include_data_products = planned_remote.includes_data_product_capture
    include_glossary_terms = planned_remote.includes_glossary_term_capture
    include_data_assets = planned_remote.includes_data_asset_capture
    include_data_columns = planned_remote.includes_data_column_capture

    rel_dp_asset = False
    rel_term_asset = False
    rel_term_column = False
    if coverage is not None and coverage.includes_governance_relationships:
        rel_dp_asset = coverage.governance_relationship_data_product_to_data_asset
        rel_term_asset = coverage.governance_relationship_glossary_term_to_data_asset
        rel_term_column = coverage.governance_relationship_glossary_term_to_data_column

    if include_data_products and (
        CAPTURED_RESOURCE_TYPE_DATA_PRODUCT not in planned_remote.captured_resource_types
    ):
        raise RemoteStateError(
            "remote_state.invalid_capture_marker",
            "planned remote claims data product capture without marker",
        )
    if include_glossary_terms and (
        CAPTURED_RESOURCE_TYPE_GLOSSARY_TERM not in planned_remote.captured_resource_types
    ):
        raise RemoteStateError(
            "remote_state.invalid_capture_marker",
            "planned remote claims glossary term capture without marker",
        )

    return UnifiedCatalogCaptureRecipeV3(
        include_data_products=include_data_products,
        include_glossary_terms=include_glossary_terms,
        include_data_assets=include_data_assets,
        include_data_columns=include_data_columns,
        include_relationship_data_product_to_data_asset=rel_dp_asset,
        include_relationship_glossary_term_to_data_asset=rel_term_asset,
        include_relationship_glossary_term_to_data_column=rel_term_column,
    )
