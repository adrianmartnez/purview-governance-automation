"""Unit tests for PurviewUnifiedCatalogClient using injected MockTransport."""

from __future__ import annotations

import httpx
import pytest
from tests.auth.fakes import FakeTokenCredential

from purview_governance.auth import PurviewAuthorizationProvider
from purview_governance.unified_catalog import (
    UNIFIED_CATALOG_API_VERSION,
    UNIFIED_CATALOG_PRODUCTION_ENDPOINT,
    UNIFIED_CATALOG_PRODUCTION_HOST,
    PurviewUnifiedCatalogClient,
    UnifiedCatalogHttpError,
    UnifiedCatalogPaginationError,
    UnifiedCatalogRequestBuildError,
    UnifiedCatalogResponseError,
    normalize_unified_catalog_endpoint,
)
from purview_governance.unified_catalog.constants import (
    BUSINESS_DOMAINS_PATH,
    CONNECT_TIMEOUT_SECONDS,
    DEFAULT_TIMEOUT,
    READ_TIMEOUT_SECONDS,
)

AUTH_TOKEN = "SECRET_SENTINEL_unified-catalog-unit-9f3c"


def _provider(token: str = AUTH_TOKEN) -> PurviewAuthorizationProvider:
    return PurviewAuthorizationProvider(FakeTokenCredential(token))  # type: ignore[arg-type]


def _client(handler: object) -> PurviewUnifiedCatalogClient:
    return PurviewUnifiedCatalogClient(
        UNIFIED_CATALOG_PRODUCTION_ENDPOINT,
        _provider(),
        transport=httpx.MockTransport(handler),  # type: ignore[arg-type]
    )


def test_public_constructor_rejects_arbitrary_host() -> None:
    with pytest.raises(UnifiedCatalogRequestBuildError):
        PurviewUnifiedCatalogClient(
            "https://evil.example.com",
            _provider(),
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"value": []})),
        )


def test_client_invariants_follow_redirects_and_timeouts() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"value": []})

    with _client(handler) as client:
        assert client.follow_redirects is False
        assert client.timeout == DEFAULT_TIMEOUT
        assert client.timeout.connect == CONNECT_TIMEOUT_SECONDS
        assert client.timeout.read == READ_TIMEOUT_SECONDS
        assert client.trust_env is True
        assert client.target_endpoint == UNIFIED_CATALOG_PRODUCTION_ENDPOINT
        assert normalize_unified_catalog_endpoint(client.target_endpoint) == (
            UNIFIED_CATALOG_PRODUCTION_ENDPOINT
        )


def test_enumerate_one_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == BUSINESS_DOMAINS_PATH
        assert request.url.params["api-version"] == UNIFIED_CATALOG_API_VERSION
        assert request.headers["Authorization"] == f"Bearer {AUTH_TOKEN}"
        assert request.headers["Accept"] == "application/json"
        assert request.url.host == UNIFIED_CATALOG_PRODUCTION_HOST
        return httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "7e74f902-62f5-49f4-8258-92ed2b8537ba",
                        "name": "fictional-domain",
                    }
                ]
            },
        )

    with _client(handler) as client:
        result = client.enumerate_business_domains()
    assert result.item_count == 1
    assert result.items[0]["name"] == "fictional-domain"


def test_enumerate_paginated_follows_next_link_with_skip_token() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if "$skipToken" not in request.url.params:
            return httpx.Response(
                200,
                json={
                    "value": [{"id": "11111111-1111-1111-1111-111111111111", "name": "page-one"}],
                    "nextLink": (
                        f"{UNIFIED_CATALOG_PRODUCTION_ENDPOINT}{BUSINESS_DOMAINS_PATH}"
                        f"?api-version={UNIFIED_CATALOG_API_VERSION}&$skipToken=fictional-token"
                    ),
                },
            )
        assert request.url.params["$skipToken"] == "fictional-token"
        return httpx.Response(
            200,
            json={"value": [{"id": "22222222-2222-2222-2222-222222222222", "name": "page-two"}]},
        )

    with _client(handler) as client:
        result = client.enumerate_business_domains()
    assert [item["name"] for item in result.items] == ["page-one", "page-two"]
    assert len(calls) == 2


def test_enumerate_rejects_cross_origin_next_link() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "value": [{"id": "11111111-1111-1111-1111-111111111111"}],
                "nextLink": "https://evil.example/continue",
            },
        )

    with pytest.raises(UnifiedCatalogPaginationError), _client(handler) as client:
        client.enumerate_business_domains()


def test_enumerate_rejects_invalid_next_link_type() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"value": [], "nextLink": 123})

    with pytest.raises(UnifiedCatalogResponseError), _client(handler) as client:
        client.enumerate_business_domains()


def test_enumerate_rejects_malformed_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=b"not-json", headers={"Content-Type": "application/json"}
        )

    with pytest.raises(UnifiedCatalogResponseError), _client(handler) as client:
        client.enumerate_business_domains()


def test_enumerate_http_error_is_sanitized() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": {"message": f"secret {AUTH_TOKEN}"}})

    with pytest.raises(UnifiedCatalogHttpError) as exc, _client(handler) as client:
        client.enumerate_business_domains()
    assert exc.value.status_code == 403
    assert AUTH_TOKEN not in str(exc.value)
    assert AUTH_TOKEN not in repr(exc.value)


def test_loopback_seam_uses_literal_ip() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "127.0.0.1"
        return httpx.Response(200, json={"value": []})

    with PurviewUnifiedCatalogClient._from_loopback_base_url(
        "http://127.0.0.1:9",
        _provider(),
        transport=httpx.MockTransport(handler),
    ) as client:
        assert client.trust_env is False
        assert client.target_endpoint == UNIFIED_CATALOG_PRODUCTION_ENDPOINT
        client.enumerate_business_domains()
