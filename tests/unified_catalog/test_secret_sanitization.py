"""Secret sanitization tests for Unified Catalog client errors."""

from __future__ import annotations

import traceback

import httpx
import pytest
from tests.auth.fakes import FakeTokenCredential

from purview_governance.auth import PurviewAuthorizationProvider
from purview_governance.unified_catalog import (
    UNIFIED_CATALOG_PRODUCTION_ENDPOINT,
    PurviewUnifiedCatalogClient,
    UnifiedCatalogHttpError,
)

AUTH_TOKEN = "SECRET_SENTINEL_unified-catalog-client-9f3c"


def _provider() -> PurviewAuthorizationProvider:
    return PurviewAuthorizationProvider(FakeTokenCredential(AUTH_TOKEN))  # type: ignore[arg-type]


def test_http_error_does_not_leak_authorization_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == f"Bearer {AUTH_TOKEN}"
        return httpx.Response(500, json={"error": {"message": f"leak {AUTH_TOKEN}"}})

    with (
        pytest.raises(UnifiedCatalogHttpError) as exc,
        PurviewUnifiedCatalogClient(
            UNIFIED_CATALOG_PRODUCTION_ENDPOINT,
            _provider(),
            transport=httpx.MockTransport(handler),
        ) as client,
    ):
        client.enumerate_business_domains()

    assert AUTH_TOKEN not in str(exc.value)
    assert AUTH_TOKEN not in repr(exc.value)
    tb = "".join(traceback.format_exception(type(exc.value), exc.value, exc.value.__traceback__))
    assert AUTH_TOKEN not in tb
