"""Fail-closed Unified Catalog production endpoint normalization."""

from __future__ import annotations

from urllib.parse import urlsplit

from purview_governance.unified_catalog.constants import (
    UNIFIED_CATALOG_PRODUCTION_ENDPOINT,
    UNIFIED_CATALOG_PRODUCTION_HOST,
)
from purview_governance.unified_catalog.errors import UnifiedCatalogRequestBuildError


def normalize_unified_catalog_endpoint(raw_endpoint: object) -> str:
    """Normalize and validate the documented Unified Catalog production endpoint.

    Only ``https://api.purview-service.microsoft.com`` is accepted. Loopback
    contract tests must use the package-private loopback client seam instead.
    """
    if not isinstance(raw_endpoint, str) or not raw_endpoint.strip():
        raise UnifiedCatalogRequestBuildError(
            "unified_catalog.invalid_endpoint",
            "endpoint must be a non-empty string",
        )

    endpoint = raw_endpoint.strip()
    try:
        parts = urlsplit(endpoint)
        hostname = parts.hostname
        port = parts.port
    except ValueError:
        raise UnifiedCatalogRequestBuildError(
            "unified_catalog.invalid_endpoint",
            "endpoint is not a valid https URL",
        ) from None

    if parts.scheme.lower() != "https":
        raise UnifiedCatalogRequestBuildError(
            "unified_catalog.invalid_endpoint",
            "endpoint must use https",
        )
    if not hostname:
        raise UnifiedCatalogRequestBuildError(
            "unified_catalog.invalid_endpoint",
            "endpoint must include a hostname",
        )
    if parts.username is not None or parts.password is not None:
        raise UnifiedCatalogRequestBuildError(
            "unified_catalog.invalid_endpoint",
            "endpoint must not include userinfo",
        )
    if parts.query:
        raise UnifiedCatalogRequestBuildError(
            "unified_catalog.invalid_endpoint",
            "endpoint must not include a query string",
        )
    if parts.fragment:
        raise UnifiedCatalogRequestBuildError(
            "unified_catalog.invalid_endpoint",
            "endpoint must not include a fragment",
        )

    path_part = parts.path or ""
    if path_part not in {"", "/"}:
        raise UnifiedCatalogRequestBuildError(
            "unified_catalog.invalid_endpoint",
            "endpoint must not include a path",
        )

    host = hostname.lower()
    if host != UNIFIED_CATALOG_PRODUCTION_HOST:
        raise UnifiedCatalogRequestBuildError(
            "unified_catalog.unsupported_endpoint_host",
            "endpoint host is not the documented Unified Catalog service host",
        )

    if port is not None and port != 443:
        raise UnifiedCatalogRequestBuildError(
            "unified_catalog.invalid_endpoint",
            "endpoint must not include a non-default port",
        )

    _ = UNIFIED_CATALOG_PRODUCTION_ENDPOINT  # canonical documented form
    return UNIFIED_CATALOG_PRODUCTION_ENDPOINT
