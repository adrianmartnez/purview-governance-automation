"""Remote-state v3 capture compatibility tests for Data Products and Glossary Terms."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from purview_governance.remote_state.errors import RemoteStateError
from purview_governance.remote_state.service import capture_unified_catalog_remote_state_v3
from purview_governance.unified_catalog.constants import UNIFIED_CATALOG_PRODUCTION_ENDPOINT
from purview_governance.unified_catalog.errors import UnifiedCatalogHttpError
from tests.contract.unified_catalog_client_helpers import make_loopback_unified_catalog_client
from tests.contract.unified_catalog_server import (
    fictional_business_domain_item,
    fictional_data_product_item,
    fictional_glossary_term_item,
    start_unified_catalog_contract_server,
)

TENANT_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


@dataclass(frozen=True, slots=True)
class Pr2UnifiedCatalogClient:
    """PR2-era client exposing only Business Domain enumerate."""

    _inner: object

    @property
    def target_endpoint(self) -> str:
        return UNIFIED_CATALOG_PRODUCTION_ENDPOINT

    def enumerate_business_domains(self):
        return self._inner.enumerate_business_domains()

    def close(self) -> None:
        self._inner.close()


def test_default_capture_emits_shape_a_pr2_compatible() -> None:
    domain = fictional_business_domain_item()
    with start_unified_catalog_contract_server(enumerate_items=[domain]) as server:
        client = make_loopback_unified_catalog_client(server.base_url)
        try:
            state = capture_unified_catalog_remote_state_v3(client, tenant_id=TENANT_ID)
        finally:
            client.close()

    doc = state.to_document()
    assert "capturedResourceTypes" not in doc
    assert "dataProducts" not in doc
    assert "uninterpretedDataProducts" not in doc
    assert state.includes_data_product_capture is False
    assert len(state.business_domains) == 1


def test_include_data_products_emits_shape_b() -> None:
    domain = fictional_business_domain_item()
    product = fictional_data_product_item()
    with start_unified_catalog_contract_server(
        enumerate_items=[domain],
        enumerate_data_products_items=[product],
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

    doc = state.to_document()
    assert doc["capturedResourceTypes"] == ["businessDomain", "dataProduct"]
    assert len(doc["dataProducts"]) == 1
    assert doc["uninterpretedDataProducts"] == []
    assert state.includes_data_product_capture is True


def test_data_product_list_failure_is_fail_closed() -> None:
    domain = fictional_business_domain_item()
    with start_unified_catalog_contract_server(
        enumerate_items=[domain],
        enumerate_data_products_mode="server_error",
    ) as server:
        client = make_loopback_unified_catalog_client(server.base_url)
        try:
            with pytest.raises(UnifiedCatalogHttpError):
                capture_unified_catalog_remote_state_v3(
                    client,
                    tenant_id=TENANT_ID,
                    include_data_products=True,
                )
        finally:
            client.close()


def test_pr2_client_without_enumerate_data_products_works_with_default_capture() -> None:
    domain = fictional_business_domain_item()
    with start_unified_catalog_contract_server(enumerate_items=[domain]) as server:
        inner = make_loopback_unified_catalog_client(server.base_url)
        client = Pr2UnifiedCatalogClient(inner)
        try:
            state = capture_unified_catalog_remote_state_v3(client, tenant_id=TENANT_ID)
        finally:
            client.close()

    assert len(state.business_domains) == 1
    assert state.includes_data_product_capture is False


def test_include_data_products_requires_client_capability() -> None:
    domain = fictional_business_domain_item()
    with start_unified_catalog_contract_server(enumerate_items=[domain]) as server:
        inner = make_loopback_unified_catalog_client(server.base_url)
        client = Pr2UnifiedCatalogClient(inner)
        try:
            with pytest.raises(RemoteStateError, match="missing_capability"):
                capture_unified_catalog_remote_state_v3(
                    client,
                    tenant_id=TENANT_ID,
                    include_data_products=True,
                )
        finally:
            client.close()


@dataclass(frozen=True, slots=True)
class Pr3UnifiedCatalogClient:
    """PR3-era client without Glossary Term enumerate."""

    _inner: object

    @property
    def target_endpoint(self) -> str:
        return UNIFIED_CATALOG_PRODUCTION_ENDPOINT

    def enumerate_business_domains(self):
        return self._inner.enumerate_business_domains()

    def enumerate_data_products(self):
        return self._inner.enumerate_data_products()

    def close(self) -> None:
        self._inner.close()


def test_include_glossary_terms_emits_shape_c() -> None:
    domain = fictional_business_domain_item()
    term = fictional_glossary_term_item()
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
    assert doc["uninterpretedGlossaryTerms"] == []
    assert "dataProducts" not in doc
    assert state.includes_glossary_term_capture is True


def test_include_data_products_without_glossary_terms_preserves_shape_b() -> None:
    domain = fictional_business_domain_item()
    product = fictional_data_product_item()
    with start_unified_catalog_contract_server(
        enumerate_items=[domain],
        enumerate_data_products_items=[product],
    ) as server:
        client = make_loopback_unified_catalog_client(server.base_url)
        try:
            state = capture_unified_catalog_remote_state_v3(
                client,
                tenant_id=TENANT_ID,
                include_data_products=True,
                include_glossary_terms=False,
            )
        finally:
            client.close()

    doc = state.to_document()
    assert doc["capturedResourceTypes"] == ["businessDomain", "dataProduct"]
    assert "glossaryTerms" not in doc
    assert "uninterpretedGlossaryTerms" not in doc


def test_glossary_term_list_failure_is_fail_closed() -> None:
    domain = fictional_business_domain_item()
    with start_unified_catalog_contract_server(
        enumerate_items=[domain],
        enumerate_glossary_terms_mode="server_error",
    ) as server:
        client = make_loopback_unified_catalog_client(server.base_url)
        try:
            with pytest.raises(UnifiedCatalogHttpError):
                capture_unified_catalog_remote_state_v3(
                    client,
                    tenant_id=TENANT_ID,
                    include_glossary_terms=True,
                )
        finally:
            client.close()


def test_include_glossary_terms_requires_client_capability() -> None:
    domain = fictional_business_domain_item()
    product = fictional_data_product_item()
    with start_unified_catalog_contract_server(
        enumerate_items=[domain],
        enumerate_data_products_items=[product],
    ) as server:
        inner = make_loopback_unified_catalog_client(server.base_url)
        client = Pr3UnifiedCatalogClient(inner)
        try:
            with pytest.raises(RemoteStateError, match="missing_capability"):
                capture_unified_catalog_remote_state_v3(
                    client,
                    tenant_id=TENANT_ID,
                    include_glossary_terms=True,
                )
        finally:
            client.close()
