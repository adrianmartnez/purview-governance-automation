"""Capture recipe replay Shapes A-D for apply/v3."""

from __future__ import annotations

from purview_governance.remote_state.capture_recipe import derive_capture_recipe
from purview_governance.remote_state.service import capture_unified_catalog_remote_state_v3
from tests.apply.helpers_v3 import TENANT_ID, capture_remote_for_apply, make_tenant_bound_client
from tests.contract.unified_catalog_server import (
    fictional_business_domain_item,
    fictional_data_product_item,
    fictional_glossary_term_item,
    start_unified_catalog_contract_server,
)


def test_shape_a_recipe_replay() -> None:
    domain = fictional_business_domain_item()
    with start_unified_catalog_contract_server(enumerate_items=[domain]) as server:
        client = make_tenant_bound_client(server.base_url)
        try:
            planned = capture_remote_for_apply(client)
            recipe = derive_capture_recipe(planned)
            replayed = capture_unified_catalog_remote_state_v3(
                client,
                tenant_id=TENANT_ID,
                include_data_products=recipe.include_data_products,
                include_glossary_terms=recipe.include_glossary_terms,
                include_data_assets=recipe.include_data_assets,
                include_data_columns=recipe.include_data_columns,
                include_relationship_data_product_to_data_asset=recipe.include_relationship_data_product_to_data_asset,
                include_relationship_glossary_term_to_data_asset=recipe.include_relationship_glossary_term_to_data_asset,
                include_relationship_glossary_term_to_data_column=recipe.include_relationship_glossary_term_to_data_column,
            )
        finally:
            client.close()
    assert replayed.material_state_identity == planned.material_state_identity


def test_shape_b_recipe_replay() -> None:
    domain = fictional_business_domain_item()
    product = fictional_data_product_item()
    with start_unified_catalog_contract_server(
        enumerate_items=[domain],
        enumerate_data_products_items=[product],
    ) as server:
        client = make_tenant_bound_client(server.base_url)
        try:
            planned = capture_remote_for_apply(client, include_data_products=True)
            recipe = derive_capture_recipe(planned)
            replayed = capture_unified_catalog_remote_state_v3(
                client,
                tenant_id=TENANT_ID,
                include_data_products=recipe.include_data_products,
                include_glossary_terms=recipe.include_glossary_terms,
                include_data_assets=recipe.include_data_assets,
                include_data_columns=recipe.include_data_columns,
                include_relationship_data_product_to_data_asset=recipe.include_relationship_data_product_to_data_asset,
                include_relationship_glossary_term_to_data_asset=recipe.include_relationship_glossary_term_to_data_asset,
                include_relationship_glossary_term_to_data_column=recipe.include_relationship_glossary_term_to_data_column,
            )
        finally:
            client.close()
    assert replayed.material_state_identity == planned.material_state_identity


def test_shape_c_recipe_replay() -> None:
    domain = fictional_business_domain_item()
    term = fictional_glossary_term_item()
    with start_unified_catalog_contract_server(
        enumerate_items=[domain],
        enumerate_glossary_terms_items=[term],
    ) as server:
        client = make_tenant_bound_client(server.base_url)
        try:
            planned = capture_remote_for_apply(client, include_glossary_terms=True)
            recipe = derive_capture_recipe(planned)
            replayed = capture_unified_catalog_remote_state_v3(
                client,
                tenant_id=TENANT_ID,
                include_data_products=recipe.include_data_products,
                include_glossary_terms=recipe.include_glossary_terms,
                include_data_assets=recipe.include_data_assets,
                include_data_columns=recipe.include_data_columns,
                include_relationship_data_product_to_data_asset=recipe.include_relationship_data_product_to_data_asset,
                include_relationship_glossary_term_to_data_asset=recipe.include_relationship_glossary_term_to_data_asset,
                include_relationship_glossary_term_to_data_column=recipe.include_relationship_glossary_term_to_data_column,
            )
        finally:
            client.close()
    assert replayed.material_state_identity == planned.material_state_identity


def test_shape_d_recipe_replay() -> None:
    domain = fictional_business_domain_item()
    product = fictional_data_product_item()
    term = fictional_glossary_term_item()
    with start_unified_catalog_contract_server(
        enumerate_items=[domain],
        enumerate_data_products_items=[product],
        enumerate_glossary_terms_items=[term],
    ) as server:
        client = make_tenant_bound_client(server.base_url)
        try:
            planned = capture_remote_for_apply(
                client,
                include_data_products=True,
                include_glossary_terms=True,
            )
            recipe = derive_capture_recipe(planned)
            replayed = capture_unified_catalog_remote_state_v3(
                client,
                tenant_id=TENANT_ID,
                include_data_products=recipe.include_data_products,
                include_glossary_terms=recipe.include_glossary_terms,
                include_data_assets=recipe.include_data_assets,
                include_data_columns=recipe.include_data_columns,
                include_relationship_data_product_to_data_asset=recipe.include_relationship_data_product_to_data_asset,
                include_relationship_glossary_term_to_data_asset=recipe.include_relationship_glossary_term_to_data_asset,
                include_relationship_glossary_term_to_data_column=recipe.include_relationship_glossary_term_to_data_column,
            )
        finally:
            client.close()
    assert replayed.material_state_identity == planned.material_state_identity
