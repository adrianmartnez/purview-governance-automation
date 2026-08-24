"""Offline Unified Catalog Data Products v3 remote-state contract tests."""

from __future__ import annotations

import pytest

from purview_governance.config.service_v3 import validate_config_v3_text
from purview_governance.plan.service_v3 import build_governance_plan_v3
from purview_governance.remote_state.service import capture_unified_catalog_remote_state_v3
from purview_governance.unified_catalog.constants import (
    DATA_PRODUCTS_PATH,
    UNIFIED_CATALOG_PRODUCTION_ENDPOINT,
)
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
OWNER_ID = "30000000-0000-4000-8000-000000000001"


def test_capture_v3_multi_data_product_deterministic() -> None:
    domain = fictional_business_domain_item(domain_id=DOMAIN_ID, name="fictional-domain")
    items = [
        fictional_data_product_item(
            product_id="40000000-0000-4000-8000-000000000002",
            name="product-b",
            domain_id=DOMAIN_ID,
        ),
        fictional_data_product_item(
            product_id=PRODUCT_ID,
            name="product-a",
            domain_id=DOMAIN_ID,
        ),
    ]
    with start_unified_catalog_contract_server(
        enumerate_items=[domain],
        enumerate_data_products_items=items,
    ) as server:
        client = make_loopback_unified_catalog_client(server.base_url)
        try:
            state = capture_unified_catalog_remote_state_v3(
                client,
                tenant_id=TENANT_ID,
                include_data_products=True,
            )
        finally:
            client.close()

    assert state.target_context.tenant_id == TENANT_ID
    assert state.target_context.endpoint == UNIFIED_CATALOG_PRODUCTION_ENDPOINT
    assert state.includes_data_product_capture is True
    assert len(state.data_products) == 2
    assert [product.id for product in state.data_products] == sorted(
        product.id for product in state.data_products
    )

    canonical_a = state.to_canonical_json()
    with start_unified_catalog_contract_server(
        enumerate_items=[domain],
        enumerate_data_products_items=list(reversed(items)),
    ) as server2:
        client2 = make_loopback_unified_catalog_client(server2.base_url)
        try:
            state2 = capture_unified_catalog_remote_state_v3(
                client2,
                tenant_id=TENANT_ID,
                include_data_products=True,
            )
        finally:
            client2.close()
    assert state2.to_canonical_json() == canonical_a


def test_data_products_route_records_api_version_and_auth() -> None:
    domain = fictional_business_domain_item(domain_id=DOMAIN_ID)
    product = fictional_data_product_item(product_id=PRODUCT_ID, domain_id=DOMAIN_ID)
    with start_unified_catalog_contract_server(
        enumerate_items=[domain],
        enumerate_data_products_items=[product],
    ) as server:
        client = make_loopback_unified_catalog_client(server.base_url)
        try:
            capture_unified_catalog_remote_state_v3(
                client,
                tenant_id=TENANT_ID,
                include_data_products=True,
            )
        finally:
            client.close()

    dp_requests = [
        record for record in server.state.recordings if record.path == DATA_PRODUCTS_PATH
    ]
    assert len(dp_requests) == 1
    assert dp_requests[0].authorization_present is True
    assert dp_requests[0].authorization_valid is True
    assert dp_requests[0].api_version is not None


def test_end_to_end_config_remote_plan_v3_data_product_no_op() -> None:
    domain = fictional_business_domain_item(
        domain_id=DOMAIN_ID,
        name="fictional-domain",
    )
    domain["type"] = "DataDomain"
    product = fictional_data_product_item(
        product_id=PRODUCT_ID,
        name="fictional-sales-product",
        domain_id=DOMAIN_ID,
        owner_id=OWNER_ID,
    )
    config_text = f"""apiVersion: purview-governance-config/v3
target:
  surface: unifiedCatalog
  tenantId: {TENANT_ID}
authentication:
  strategy: defaultAzureCredential
resources:
  - type: businessDomain
    id: {DOMAIN_ID}
    properties:
      name: fictional-domain
      status: PUBLISHED
      type: DataDomain
  - type: dataProduct
    id: {PRODUCT_ID}
    properties:
      name: fictional-sales-product
      domain: {DOMAIN_ID}
      type: Master
      description: Fictional data product description
      businessUse: Fictional business use
      owners:
        - id: {OWNER_ID}
"""
    config = validate_config_v3_text(config_text, format_hint="yaml")
    with start_unified_catalog_contract_server(
        enumerate_items=[domain],
        enumerate_data_products_items=[product],
    ) as server:
        client = make_loopback_unified_catalog_client(server.base_url)
        try:
            remote = capture_unified_catalog_remote_state_v3(
                client,
                tenant_id=TENANT_ID,
                include_data_products=True,
            )
        finally:
            client.close()

    plan = build_governance_plan_v3(config, remote)
    assert plan.execution_eligibility == "ready"
    assert plan.summary.no_op >= 2
    assert plan.summary.operations == 0
