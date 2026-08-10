"""Unit tests for PurviewScanningClient using injected MockTransport."""

from __future__ import annotations

import inspect
import json
import math
import traceback
from collections.abc import Iterator, Mapping
from typing import Any

import httpx
import pytest

from purview_governance.auth import PurviewAuthorizationProvider
from purview_governance.config import ConfigValidationError
from purview_governance.scanning import (
    SCANNING_API_VERSION,
    PurviewHttpError,
    PurviewPaginationError,
    PurviewRequestBuildError,
    PurviewRequestError,
    PurviewResponseError,
    PurviewScanningClient,
    PurviewTimeoutError,
)
from purview_governance.scanning.constants import (
    CONNECT_TIMEOUT_SECONDS,
    DEFAULT_TIMEOUT,
    MAX_LIST_PAGES,
    READ_TIMEOUT_SECONDS,
)
from tests.auth.fakes import FakeTokenCredential

ENDPOINT = "https://example.purview.azure.com"
AUTH_TOKEN = "SECRET_SENTINEL_scanning-client-unit-9f3c"


class _HostileMapping(Mapping[str, Any]):
    """Mapping whose materialization leaks a sentinel via the exception message."""

    def __iter__(self) -> Iterator[str]:
        raise RuntimeError(f"materialize boom {AUTH_TOKEN}")

    def __len__(self) -> int:
        return 0

    def __getitem__(self, key: str) -> Any:
        raise KeyError(key)


def _provider(token: str = AUTH_TOKEN) -> PurviewAuthorizationProvider:
    return PurviewAuthorizationProvider(FakeTokenCredential(token))  # type: ignore[arg-type]


def _client(handler: Any) -> PurviewScanningClient:
    return PurviewScanningClient(
        ENDPOINT,
        _provider(),
        transport=httpx.MockTransport(handler),
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


def test_import_does_not_require_network() -> None:
    import purview_governance.scanning as scanning

    assert scanning.SCANNING_API_VERSION == "2023-09-01"


def test_list_one_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/scan/datasources"
        assert request.url.params["api-version"] == SCANNING_API_VERSION
        assert request.headers["Authorization"] == f"Bearer {AUTH_TOKEN}"
        assert request.headers["Accept"] == "application/json"
        assert request.url.host == "example.purview.azure.com"
        return httpx.Response(
            200,
            json={"value": [{"name": "ds1", "kind": "AzureStorage"}], "count": 1},
        )

    with _client(handler) as client:
        result = client.list_data_sources()
    assert result.item_count == 1
    assert result.items[0]["name"] == "ds1"


def test_list_paginated_does_not_sum_count() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if request.url.path == "/scan/datasources" and "page" not in request.url.params:
            return httpx.Response(
                200,
                json={
                    "value": [{"name": "a"}],
                    "count": 99,
                    "nextLink": (
                        f"{ENDPOINT}/scan/datasources?api-version={SCANNING_API_VERSION}&page=2"
                    ),
                },
            )
        return httpx.Response(
            200,
            json={"value": [{"name": "b"}], "count": 1},
        )

    with _client(handler) as client:
        result = client.list_data_sources()
    assert len(calls) == 2
    assert result.item_count == 2
    assert [item["name"] for item in result.items] == ["a", "b"]
    # Remote counts must not be summed into item_count.
    assert result.item_count != 99 + 1


def test_list_rejects_relative_next_link_before_follow() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json={"value": [{"name": "a"}], "nextLink": "/scan/datasources?page=2"},
        )

    with _client(handler) as client, pytest.raises(PurviewPaginationError):
        client.list_data_sources()
    assert calls == 1


def test_list_rejects_cross_origin_next_link_before_follow() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json={
                "value": [{"name": "a"}],
                "nextLink": "https://evil.example/scan/datasources",
            },
        )

    with _client(handler) as client, pytest.raises(PurviewPaginationError):
        client.list_data_sources()
    assert calls == 1


def test_list_rejects_repeated_next_link() -> None:
    link = f"{ENDPOINT}/scan/datasources?api-version={SCANNING_API_VERSION}&page=2"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"value": [{"name": "a"}], "nextLink": link},
        )

    with _client(handler) as client, pytest.raises(PurviewPaginationError) as exc_info:
        client.list_data_sources()
    assert exc_info.value.code == "scanning.pagination_loop"


def test_list_page_cap() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params.get("p", "0"))
        next_page = page + 1
        return httpx.Response(
            200,
            json={
                "value": [{"name": f"n{page}"}],
                "nextLink": (
                    f"{ENDPOINT}/scan/datasources?api-version={SCANNING_API_VERSION}&p={next_page}"
                ),
            },
        )

    with _client(handler) as client, pytest.raises(PurviewPaginationError) as exc_info:
        client.list_data_sources()
    assert exc_info.value.code == "scanning.pagination_limit_exceeded"
    assert MAX_LIST_PAGES >= 1


def test_get_data_source_success_and_defensive_copy() -> None:
    stored: dict[str, Any] = {"name": "myDataSource", "nested": {"x": 1}}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/scan/datasources/myDataSource"
        return httpx.Response(200, json=stored)

    with _client(handler) as client:
        first = client.get_data_source("myDataSource")
        first["nested"]["x"] = 99
        second = client.get_data_source("myDataSource")
    assert second["nested"]["x"] == 1
    assert first["nested"]["x"] == 99


def test_get_rejects_non_200() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": {"code": "NotFound"}})

    with _client(handler) as client, pytest.raises(PurviewHttpError) as exc_info:
        client.get_data_source("missingSource")
    assert exc_info.value.status_code == 404
    assert AUTH_TOKEN not in str(exc_info.value)
    assert AUTH_TOKEN not in repr(exc_info.value)


def test_create_or_replace_canonical_json_and_status() -> None:
    bodies: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(request.content)
        assert request.method == "PUT"
        assert request.headers["Content-Type"] == "application/json"
        assert request.url.params["api-version"] == SCANNING_API_VERSION
        return httpx.Response(201, json={"name": "myDataSource", "kind": "AzureStorage"})

    payload = {
        "kind": "AzureStorage",
        "properties": {"endpoint": "https://x.blob.core.windows.net/"},
    }
    with _client(handler) as client:
        result = client._create_or_replace_data_source("myDataSource", payload)
    assert result.name == "myDataSource"
    assert result.status_code == 201
    expected = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    assert bodies[0] == expected


def test_create_or_replace_confirmed_write_ignores_invalid_json_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=b"not-json", headers={"Content-Type": "application/json"}
        )

    payload = {"kind": "AzureStorage"}
    with _client(handler) as client:
        receipt = client._create_or_replace_data_source("myDataSource", payload)
    assert receipt.status_code == 200
    assert receipt.name == "myDataSource"


def _assert_sanitized_public_error(error: BaseException) -> None:
    assert error.__cause__ is None
    assert error.__context__ is None
    text = f"{error!s}{error!r}{''.join(traceback.format_exception(error))}"
    assert AUTH_TOKEN not in text
    assert not any(
        value is not None and AUTH_TOKEN in str(value) for _name, value in vars(error).items()
    )


def test_create_or_replace_rejects_nan() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("must not send request")

    with _client(handler) as client, pytest.raises(PurviewRequestBuildError) as exc_info:
        client._create_or_replace_data_source(
            "myDataSource",
            {"kind": "AzureStorage", "n": math.nan},
        )
    error = exc_info.value
    assert error.code == "scanning.invalid_json_payload"
    assert error.message == "request body is not strict JSON-serializable"
    _assert_sanitized_public_error(error)


def test_create_or_replace_rejects_non_serializable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("must not send request")

    with _client(handler) as client, pytest.raises(PurviewRequestBuildError) as exc_info:
        client._create_or_replace_data_source(
            "myDataSource",
            {"kind": "AzureStorage", "bad": object()},
        )
    error = exc_info.value
    assert error.code == "scanning.invalid_json_payload"
    assert error.message == "request body is not strict JSON-serializable"
    assert "object" not in error.message
    _assert_sanitized_public_error(error)


def test_create_or_replace_hostile_mapping_sanitized() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("must not send request")

    with _client(handler) as client, pytest.raises(PurviewRequestBuildError) as exc_info:
        client._create_or_replace_data_source("myDataSource", _HostileMapping())
    error = exc_info.value
    assert error.code == "scanning.invalid_json_payload"
    assert error.message == "request body must be a JSON object mapping"
    _assert_sanitized_public_error(error)


def test_invalid_json_response() -> None:
    body = f'{{"not": "json", "leak": "{AUTH_TOKEN}"'.encode()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=body,
            headers={"Content-Type": "application/json"},
        )

    with _client(handler) as client, pytest.raises(PurviewResponseError) as exc_info:
        client.get_data_source("myDataSource")
    error = exc_info.value
    assert error.code == "scanning.invalid_json_response"
    _assert_sanitized_public_error(error)


def test_invalid_list_shape() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"value": "nope"})

    with _client(handler) as client, pytest.raises(PurviewResponseError):
        client.list_data_sources()


def test_list_rejects_bool_count() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"value": [], "count": True})

    with _client(handler) as client, pytest.raises(PurviewResponseError):
        client.list_data_sources()


def test_redirect_treated_as_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": "https://evil.example/"})

    with _client(handler) as client, pytest.raises(PurviewHttpError) as exc_info:
        client.get_data_source("myDataSource")
    assert exc_info.value.status_code == 302


def test_transport_failure_and_timeout() -> None:
    def fail_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    with _client(fail_handler) as client, pytest.raises(PurviewRequestError) as exc_info:
        client.list_data_sources()
    assert AUTH_TOKEN not in str(exc_info.value)
    assert AUTH_TOKEN not in repr(exc_info.value)

    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with _client(timeout_handler) as client, pytest.raises(PurviewTimeoutError):
        client.list_data_sources()


def test_mock_transport_rejects_purview_azure_com_escape() -> None:
    """Network guard: unit handler must not be pointed at live Purview hosts unexpectedly."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host.endswith("purview.azure.com")
        # Still a mock — no real network. Assert host is the configured test endpoint.
        assert request.url.host == "example.purview.azure.com"
        return httpx.Response(200, json={"value": []})

    with _client(handler) as client:
        client.list_data_sources()


def test_errors_do_not_embed_authorization_or_bodies() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            500,
            json={"error": {"message": AUTH_TOKEN, "secret": "leak"}},
            headers={
                "x-ms-request-id": AUTH_TOKEN,
                "x-ms-error-code": AUTH_TOKEN,
                "Authorization": f"Bearer {AUTH_TOKEN}",
            },
        )

    with _client(handler) as client, pytest.raises(PurviewHttpError) as exc_info:
        client.get_data_source("myDataSource")
    error = exc_info.value
    assert not hasattr(error, "request_id") or getattr(error, "request_id", None) is None
    assert not hasattr(error, "error_code") or getattr(error, "error_code", None) is None
    assert "leak" not in str(error)
    _assert_sanitized_public_error(error)


def test_https_required_for_public_constructor() -> None:
    with pytest.raises(ConfigValidationError):
        PurviewScanningClient("http://127.0.0.1:9", _provider())


def test_public_constructor_signature_has_no_insecure_bypass() -> None:
    params = inspect.signature(PurviewScanningClient.__init__).parameters
    assert "_origin" not in params
    assert "_trust_env" not in params
    assert "trust_env" not in params
    assert "allow_insecure" not in params
    assert set(params) == {"self", "endpoint", "auth_provider", "transport"}


def test_loopback_seam_sets_trust_env_false() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"value": []})

    client = PurviewScanningClient._from_loopback_base_url(
        "http://127.0.0.1:8123",
        _provider(),
        logical_target_endpoint="https://account.purview.azure.com",
        transport=httpx.MockTransport(handler),
    )
    try:
        assert client.trust_env is False
        assert client.follow_redirects is False
        assert client.base_url == "http://127.0.0.1:8123"
        assert client.target_endpoint == "https://account.purview.azure.com"
        client.list_data_sources()
    finally:
        client.close()


def test_loopback_seam_not_in_all() -> None:
    import purview_governance.scanning as scanning

    assert "_from_loopback_base_url" not in scanning.__all__
    assert not hasattr(scanning, "_from_loopback_base_url")
