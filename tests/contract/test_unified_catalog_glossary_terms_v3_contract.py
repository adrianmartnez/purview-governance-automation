"""Offline Unified Catalog Glossary Terms v3 remote-state contract tests."""

from __future__ import annotations

import pytest

from purview_governance.remote_state.service import capture_unified_catalog_remote_state_v3
from purview_governance.unified_catalog.constants import (
    GLOSSARY_TERMS_PATH,
    UNIFIED_CATALOG_PRODUCTION_ENDPOINT,
)
from tests.contract.unified_catalog_client_helpers import make_loopback_unified_catalog_client
from tests.contract.unified_catalog_server import (
    fictional_business_domain_item,
    fictional_glossary_term_item,
    start_unified_catalog_contract_server,
)

pytestmark = pytest.mark.api_contract

TENANT_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
DOMAIN_ID = "10000000-0000-4000-8000-000000000001"
TERM_ID = "50000000-0000-4000-8000-000000000001"
PARENT_ID = "50000000-0000-4000-8000-000000000002"


def test_capture_v3_multi_glossary_term_deterministic() -> None:
    domain = fictional_business_domain_item(domain_id=DOMAIN_ID, name="fictional-domain")
    items = [
        fictional_glossary_term_item(
            term_id=PARENT_ID,
            name="parent-term",
            domain_id=DOMAIN_ID,
        ),
        fictional_glossary_term_item(
            term_id=TERM_ID,
            name="child-term",
            domain_id=DOMAIN_ID,
            parent_id=PARENT_ID,
            acronyms=["REV"],
        ),
    ]
    with start_unified_catalog_contract_server(
        enumerate_items=[domain],
        enumerate_glossary_terms_items=items,
    ) as server:
        client = make_loopback_unified_catalog_client(server.base_url)
        try:
            state = capture_unified_catalog_remote_state_v3(
                client,
                tenant_id=TENANT_ID,
                include_glossary_terms=True,
            )
        finally:
            client.close()

    assert state.includes_glossary_term_capture is True
    assert len(state.glossary_terms) == 2
    assert [term.id for term in state.glossary_terms] == sorted(
        term.id for term in state.glossary_terms
    )

    canonical_a = state.to_canonical_json()
    with start_unified_catalog_contract_server(
        enumerate_items=[domain],
        enumerate_glossary_terms_items=list(reversed(items)),
    ) as server2:
        client2 = make_loopback_unified_catalog_client(server2.base_url)
        try:
            state2 = capture_unified_catalog_remote_state_v3(
                client2,
                tenant_id=TENANT_ID,
                include_glossary_terms=True,
            )
        finally:
            client2.close()
    assert state2.to_canonical_json() == canonical_a


def test_glossary_terms_route_records_api_version_and_auth() -> None:
    domain = fictional_business_domain_item(domain_id=DOMAIN_ID)
    term = fictional_glossary_term_item(term_id=TERM_ID, domain_id=DOMAIN_ID)
    with start_unified_catalog_contract_server(
        enumerate_items=[domain],
        enumerate_glossary_terms_items=[term],
    ) as server:
        client = make_loopback_unified_catalog_client(server.base_url)
        try:
            capture_unified_catalog_remote_state_v3(
                client,
                tenant_id=TENANT_ID,
                include_glossary_terms=True,
            )
        finally:
            client.close()

    gt_requests = [
        record for record in server.state.recordings if record.path == GLOSSARY_TERMS_PATH
    ]
    assert len(gt_requests) == 1
    assert gt_requests[0].authorization_present is True
    assert gt_requests[0].authorization_valid is True
    assert gt_requests[0].api_version is not None


def test_capture_shape_c_emits_glossary_term_marker() -> None:
    domain = fictional_business_domain_item(domain_id=DOMAIN_ID)
    term = fictional_glossary_term_item(term_id=TERM_ID, domain_id=DOMAIN_ID)
    with start_unified_catalog_contract_server(
        enumerate_items=[domain],
        enumerate_glossary_terms_items=[term],
    ) as server:
        client = make_loopback_unified_catalog_client(server.base_url)
        try:
            state = capture_unified_catalog_remote_state_v3(
                client,
                tenant_id=TENANT_ID,
                include_glossary_terms=True,
            )
        finally:
            client.close()

    doc = state.to_document()
    assert doc["capturedResourceTypes"] == ["businessDomain", "glossaryTerm"]
    assert len(doc["glossaryTerms"]) == 1
    assert state.target_context.endpoint == UNIFIED_CATALOG_PRODUCTION_ENDPOINT
