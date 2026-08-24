"""Test-only helpers to construct a loopback Unified Catalog client."""

from __future__ import annotations

from purview_governance.auth import PurviewAuthorizationProvider
from purview_governance.unified_catalog.client import PurviewUnifiedCatalogClient
from purview_governance.unified_catalog.constants import UNIFIED_CATALOG_PRODUCTION_ENDPOINT
from tests.auth.fakes import FakeTokenCredential
from tests.contract.auth import AUTH_SENTINEL


def make_loopback_unified_catalog_client(
    base_url: str,
    *,
    logical_target_endpoint: str = UNIFIED_CATALOG_PRODUCTION_ENDPOINT,
    auth_provider: PurviewAuthorizationProvider | None = None,
) -> PurviewUnifiedCatalogClient:
    """Build a package client bound to a literal loopback HTTP contract server."""
    if auth_provider is None:
        token = AUTH_SENTINEL.removeprefix("Bearer ").strip()
        auth_provider = PurviewAuthorizationProvider(FakeTokenCredential(token))  # type: ignore[arg-type]
    return PurviewUnifiedCatalogClient._from_loopback_base_url(
        base_url,
        auth_provider,
        logical_target_endpoint=logical_target_endpoint,
    )
