"""Offline Unified Catalog Business Domains v3 remote-state contract tests."""

from __future__ import annotations

import pytest

from purview_governance.config.service_v3 import validate_config_v3_text
from purview_governance.plan.service_v3 import build_governance_plan_v3
from purview_governance.remote_state.service import capture_unified_catalog_remote_state_v3
from purview_governance.unified_catalog.constants import UNIFIED_CATALOG_PRODUCTION_ENDPOINT
from tests.contract.unified_catalog_client_helpers import make_loopback_unified_catalog_client
from tests.contract.unified_catalog_server import (
    fictional_business_domain_item,
    start_unified_catalog_contract_server,
)

pytestmark = pytest.mark.api_contract

TENANT_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def test_capture_v3_multi_domain_deterministic() -> None:
    items = [
        fictional_business_domain_item(
            domain_id="8e74f902-62f5-49f4-8258-92ed2b8537bb",
            name="domain-b",
        ),
        fictional_business_domain_item(
            domain_id="7e74f902-62f5-49f4-8258-92ed2b8537ba",
            name="domain-a",
        ),
    ]
    with start_unified_catalog_contract_server(enumerate_items=items) as server:
        client = make_loopback_unified_catalog_client(server.base_url)
        try:
            state = capture_unified_catalog_remote_state_v3(client, tenant_id=TENANT_ID)
        finally:
            client.close()
    assert state.target_context.tenant_id == TENANT_ID
    assert state.target_context.endpoint == UNIFIED_CATALOG_PRODUCTION_ENDPOINT
    assert len(state.business_domains) == 2
    assert [d.id for d in state.business_domains] == sorted(d.id for d in state.business_domains)
    canonical_a = state.to_canonical_json()
    with start_unified_catalog_contract_server(enumerate_items=list(reversed(items))) as server2:
        client2 = make_loopback_unified_catalog_client(server2.base_url)
        try:
            state2 = capture_unified_catalog_remote_state_v3(client2, tenant_id=TENANT_ID)
        finally:
            client2.close()
    assert state2.to_canonical_json() == canonical_a


def test_end_to_end_config_remote_plan_v3() -> None:
    domain_id = "7e74f902-62f5-49f4-8258-92ed2b8537ba"
    item = fictional_business_domain_item(domain_id=domain_id, name="fictional-sales-domain")
    config_text = f"""apiVersion: purview-governance-config/v3
target:
  surface: unifiedCatalog
  tenantId: {TENANT_ID}
authentication:
  strategy: defaultAzureCredential
resources:
  - type: businessDomain
    id: {domain_id}
    properties:
      name: fictional-sales-domain
      status: PUBLISHED
      type: FunctionalUnit
"""
    config = validate_config_v3_text(config_text, format_hint="yaml")
    with start_unified_catalog_contract_server(enumerate_items=[item]) as server:
        client = make_loopback_unified_catalog_client(server.base_url)
        try:
            remote = capture_unified_catalog_remote_state_v3(client, tenant_id=TENANT_ID)
        finally:
            client.close()
    plan = build_governance_plan_v3(config, remote)
    assert plan.execution_eligibility == "ready"
    assert plan.summary.no_op >= 1
    assert plan.summary.operations == 0
