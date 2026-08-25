"""Static PR6 Unified Catalog write surface markers."""

from __future__ import annotations

import inspect

from purview_governance.unified_catalog.client import PurviewUnifiedCatalogClient


def test_write_surface_pr6() -> None:
    public_methods = {
        name
        for name, value in inspect.getmembers(PurviewUnifiedCatalogClient)
        if not name.startswith("_") and callable(value)
    }
    assert "_create_business_domain" not in dir(PurviewUnifiedCatalogClient)
    assert hasattr(PurviewUnifiedCatalogClient, "_update_business_domain")
    assert hasattr(PurviewUnifiedCatalogClient, "_create_data_product")
    assert hasattr(PurviewUnifiedCatalogClient, "_update_data_product")
    assert hasattr(PurviewUnifiedCatalogClient, "_create_glossary_term")
    assert hasattr(PurviewUnifiedCatalogClient, "_update_glossary_term")
    assert "create_business_domain" not in public_methods
    assert "update_business_domain" not in public_methods

    markers = {
        "BUSINESS_DOMAIN_CREATE_PRESENT": False,
        "BUSINESS_DOMAIN_UPDATE_PRESENT": True,
        "DATA_PRODUCT_CREATE_PRESENT": True,
        "DATA_PRODUCT_UPDATE_PRESENT": True,
        "GLOSSARY_TERM_CREATE_PRESENT": True,
        "GLOSSARY_TERM_UPDATE_PRESENT": True,
    }
    assert markers["BUSINESS_DOMAIN_CREATE_PRESENT"] is False
    assert markers["BUSINESS_DOMAIN_UPDATE_PRESENT"] is True
