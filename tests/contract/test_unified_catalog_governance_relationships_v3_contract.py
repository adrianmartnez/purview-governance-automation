"""Offline Unified Catalog governance relationships v3 contract tests."""

from __future__ import annotations

import pytest

from purview_governance.remote_state.service import capture_unified_catalog_remote_state_v3
from tests.contract.unified_catalog_client_helpers import make_loopback_unified_catalog_client
from tests.contract.unified_catalog_server import (
    fictional_business_domain_item,
    fictional_data_product_item,
    start_unified_catalog_contract_server,
)

pytestmark = pytest.mark.api_contract

TENANT_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
DOMAIN_ID = "10000000-0000-4000-8000-000000000001"
PRODUCT_ID = "40000000-0000-4000-8000-000000000001"
ASSET_TARGET = "60000000-0000-4000-8000-000000000001"


def test_data_product_to_data_asset_relationship_capture() -> None:
    domain = fictional_business_domain_item(domain_id=DOMAIN_ID)
    product = fictional_data_product_item(product_id=PRODUCT_ID, domain_id=DOMAIN_ID)
    with start_unified_catalog_contract_server(
        enumerate_items=[domain],
        enumerate_data_products_items=[product],
        data_product_relationships={
            PRODUCT_ID: [
                {"entityId": ASSET_TARGET, "relationshipType": "Related"},
            ]
        },
    ) as server:
        client = make_loopback_unified_catalog_client(server.base_url)
        try:
            state = capture_unified_catalog_remote_state_v3(
                client,
                tenant_id=TENANT_ID,
                include_data_products=True,
                include_relationship_data_product_to_data_asset=True,
            )
        finally:
            client.close()

    coverage = state.read_model_coverage
    assert coverage is not None
    assert coverage.relationship_data_product_to_data_asset
    assert len(state.governance_relationships) == 1
    edge = state.governance_relationships[0]
    assert edge.source_id == PRODUCT_ID
    assert edge.target_id == ASSET_TARGET
