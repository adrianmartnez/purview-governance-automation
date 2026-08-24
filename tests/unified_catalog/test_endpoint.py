"""Unit tests for Unified Catalog endpoint normalization."""

from __future__ import annotations

import pytest

from purview_governance.unified_catalog import (
    UNIFIED_CATALOG_PRODUCTION_ENDPOINT,
    normalize_unified_catalog_endpoint,
)
from purview_governance.unified_catalog.errors import UnifiedCatalogRequestBuildError


def test_normalize_accepts_documented_production_endpoint() -> None:
    assert (
        normalize_unified_catalog_endpoint("https://api.purview-service.microsoft.com")
        == UNIFIED_CATALOG_PRODUCTION_ENDPOINT
    )
    assert (
        normalize_unified_catalog_endpoint("https://api.purview-service.microsoft.com/")
        == UNIFIED_CATALOG_PRODUCTION_ENDPOINT
    )


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://api.purview-service.microsoft.com",
        "https://evil.example.com",
        "https://catalog-fictional.purview-service.microsoft.com",
        "https://api.purview-service.microsoft.com/path",
        "https://user:pass@api.purview-service.microsoft.com",
        "https://api.purview-service.microsoft.com?x=1",
        "",
        "not-a-url",
    ],
)
def test_normalize_rejects_unsupported_or_unsafe_endpoints(endpoint: str) -> None:
    with pytest.raises(UnifiedCatalogRequestBuildError):
        normalize_unified_catalog_endpoint(endpoint)


def test_unsupported_host_has_distinct_code() -> None:
    with pytest.raises(UnifiedCatalogRequestBuildError) as exc:
        normalize_unified_catalog_endpoint("https://evil.example.com")
    assert exc.value.code == "unified_catalog.unsupported_endpoint_host"
