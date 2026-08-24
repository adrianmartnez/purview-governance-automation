"""Real local HTTP contract tests for Unified Catalog Business Domain enumerate."""

from __future__ import annotations

import json
import traceback

import pytest

from purview_governance.unified_catalog import (
    UNIFIED_CATALOG_API_VERSION,
    UnifiedCatalogHttpError,
    UnifiedCatalogPaginationError,
    UnifiedCatalogResponseError,
)
from tests.contract.auth import AUTH_SENTINEL
from tests.contract.unified_catalog_client_helpers import make_loopback_unified_catalog_client
from tests.contract.unified_catalog_server import (
    SECRET_SENTINEL_CONTRACT_401,
    SECRET_SENTINEL_CONTRACT_403,
    SECRET_SENTINEL_CONTRACT_404,
    SECRET_SENTINEL_CONTRACT_429,
    SECRET_SENTINEL_CONTRACT_500,
    fictional_business_domain_item,
    start_unified_catalog_contract_server,
)

AUTH_RAW = AUTH_SENTINEL


def _assert_recording_has_no_raw_authorization(server) -> None:
    blob = json.dumps(
        [
            {
                "method": r.method,
                "path": r.path,
                "api_version": r.api_version,
                "accept": r.accept,
                "authorization_present": r.authorization_present,
                "authorization_valid": r.authorization_valid,
                "skip_token": r.skip_token,
                "write_only": r.write_only,
            }
            for r in server.state.recordings
        ]
    )
    assert AUTH_RAW not in blob
    assert "TEST_PURVIEW_AUTH_SENTINEL" not in blob


@pytest.mark.api_contract
def test_enumerate_requires_authorization_on_business_domains() -> None:
    import urllib.error
    import urllib.request

    with start_unified_catalog_contract_server() as server:
        url = (
            f"{server.base_url}/datagovernance/catalog/businessdomains"
            f"?api-version={UNIFIED_CATALOG_API_VERSION}"
        )
        request = urllib.request.Request(url, method="GET")
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(request)  # noqa: S310
        assert exc_info.value.code == 401
        body = exc_info.value.read().decode("utf-8")
        assert SECRET_SENTINEL_CONTRACT_401 in body
        assert AUTH_RAW not in body


@pytest.mark.api_contract
def test_enumerate_success_single_page() -> None:
    item = fictional_business_domain_item(name="contract-domain-alpha")
    with start_unified_catalog_contract_server(enumerate_items=[item]) as server:
        with make_loopback_unified_catalog_client(server.base_url) as client:
            assert client.trust_env is False
            result = client.enumerate_business_domains()
        assert result.item_count == 1
        assert result.items[0]["name"] == "contract-domain-alpha"
        rec = server.state.recordings[0]
        assert rec.method == "GET"
        assert rec.path == "/datagovernance/catalog/businessdomains"
        assert rec.api_version == UNIFIED_CATALOG_API_VERSION
        assert rec.accept == "application/json"
        assert rec.authorization_present is True
        assert rec.authorization_valid is True
        _assert_recording_has_no_raw_authorization(server)


@pytest.mark.api_contract
def test_enumerate_paginated_follows_next_link_with_skip_token() -> None:
    with start_unified_catalog_contract_server(enumerate_mode="paginated") as server:
        with make_loopback_unified_catalog_client(server.base_url) as client:
            result = client.enumerate_business_domains()
        names = [item["name"] for item in result.items]
        assert names == ["fictional-sales-domain", "fictional-page-two"]
        assert len(server.state.recordings) == 2
        assert server.state.recordings[1].skip_token == "fictional-skip-token-abc"
        _assert_recording_has_no_raw_authorization(server)


@pytest.mark.api_contract
def test_enumerate_rejects_cross_origin_next_link() -> None:
    with start_unified_catalog_contract_server(enumerate_mode="cross_origin_next_link") as server:
        with (
            make_loopback_unified_catalog_client(server.base_url) as client,
            pytest.raises(UnifiedCatalogPaginationError),
        ):
            client.enumerate_business_domains()
        _assert_recording_has_no_raw_authorization(server)


@pytest.mark.api_contract
def test_enumerate_wrong_api_version_returns_400() -> None:
    import urllib.error
    import urllib.request

    with start_unified_catalog_contract_server() as server:
        url = (
            f"{server.base_url}/datagovernance/catalog/businessdomains"
            "?api-version=2025-09-15-preview"
        )
        request = urllib.request.Request(url, method="GET", headers={"Authorization": AUTH_RAW})
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(request)  # noqa: S310
        assert exc_info.value.code == 400


@pytest.mark.api_contract
def test_enumerate_representative_http_errors_are_sanitized() -> None:
    cases = [
        ("forbidden", 403, SECRET_SENTINEL_CONTRACT_403),
        ("not_found", 404, SECRET_SENTINEL_CONTRACT_404),
        ("throttled", 429, SECRET_SENTINEL_CONTRACT_429),
        ("server_error", 500, SECRET_SENTINEL_CONTRACT_500),
    ]
    for mode, status_code, sentinel in cases:
        with start_unified_catalog_contract_server(enumerate_mode=mode) as server:
            with (
                make_loopback_unified_catalog_client(server.base_url) as client,
                pytest.raises(UnifiedCatalogHttpError) as exc,
            ):
                client.enumerate_business_domains()
            assert exc.value.status_code == status_code
            assert sentinel not in str(exc.value)
            assert sentinel not in repr(exc.value)
            tb = "".join(
                traceback.format_exception(type(exc.value), exc.value, exc.value.__traceback__)
            )
            assert sentinel not in tb
            assert AUTH_RAW not in str(exc.value)


@pytest.mark.api_contract
def test_enumerate_malformed_json_and_bad_shape() -> None:
    with (
        start_unified_catalog_contract_server(enumerate_mode="bad_json") as server,
        make_loopback_unified_catalog_client(server.base_url) as client,
        pytest.raises(UnifiedCatalogResponseError),
    ):
        client.enumerate_business_domains()
    _assert_recording_has_no_raw_authorization(server)

    with (
        start_unified_catalog_contract_server(enumerate_mode="bad_shape") as server,
        make_loopback_unified_catalog_client(server.base_url) as client,
        pytest.raises(UnifiedCatalogResponseError),
    ):
        client.enumerate_business_domains()
