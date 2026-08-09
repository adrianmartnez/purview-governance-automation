"""Tests for endpoint origin and nextLink guards."""

from __future__ import annotations

import pytest

from purview_governance.scanning.errors import PurviewPaginationError, PurviewRequestBuildError
from purview_governance.scanning.origin import (
    EndpointOrigin,
    origin_from_https_endpoint,
    origin_from_loopback_http_base_url,
    validate_absolute_same_origin_next_link,
)


def test_https_origin_from_normalized_endpoint() -> None:
    origin = origin_from_https_endpoint("https://account.purview.azure.com")
    assert origin.origin_key == ("https", "account.purview.azure.com", 443)
    assert origin.canonical_base_url == "https://account.purview.azure.com"


def test_loopback_accepts_literal_ipv4() -> None:
    origin = origin_from_loopback_http_base_url("http://127.0.0.1:8765")
    assert origin.scheme == "http"
    assert origin.host == "127.0.0.1"
    assert origin.port == 8765


def test_loopback_accepts_literal_ipv6() -> None:
    origin = origin_from_loopback_http_base_url("http://[::1]:9000")
    assert origin.host == "::1"
    assert origin.port == 9000
    assert origin.canonical_base_url == "http://[::1]:9000"


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8080",
        "https://127.0.0.1:8080",
        "http://192.168.1.1:8080",
        "http://127.0.0.1:8080/path",
        "http://user:pass@127.0.0.1:8080",
        "http://127.0.0.1:8080?x=1",
        "http://127.0.0.1:8080#frag",
    ],
)
def test_loopback_rejects_unsafe_urls(url: str) -> None:
    with pytest.raises(PurviewRequestBuildError):
        origin_from_loopback_http_base_url(url)


def test_next_link_same_origin_ok() -> None:
    origin = EndpointOrigin("https", "account.purview.azure.com", None)
    link = "https://account.purview.azure.com/scan/datasources?api-version=2023-09-01&x=1"
    assert validate_absolute_same_origin_next_link(link, origin) == link


def test_next_link_rejects_relative() -> None:
    origin = EndpointOrigin("https", "account.purview.azure.com", None)
    with pytest.raises(PurviewPaginationError) as exc_info:
        validate_absolute_same_origin_next_link("/scan/datasources?page=2", origin)
    assert exc_info.value.code == "scanning.invalid_pagination_link"


def test_next_link_rejects_cross_origin() -> None:
    origin = EndpointOrigin("https", "account.purview.azure.com", None)
    with pytest.raises(PurviewPaginationError):
        validate_absolute_same_origin_next_link(
            "https://evil.example/scan/datasources",
            origin,
        )


def test_next_link_rejects_http_downgrade() -> None:
    origin = EndpointOrigin("https", "account.purview.azure.com", None)
    with pytest.raises(PurviewPaginationError):
        validate_absolute_same_origin_next_link(
            "http://account.purview.azure.com/scan/datasources",
            origin,
        )


def test_next_link_rejects_userinfo_and_fragment() -> None:
    origin = EndpointOrigin("http", "127.0.0.1", 8080)
    with pytest.raises(PurviewPaginationError):
        validate_absolute_same_origin_next_link(
            "http://user:pass@127.0.0.1:8080/scan/datasources",
            origin,
        )
    with pytest.raises(PurviewPaginationError):
        validate_absolute_same_origin_next_link(
            "http://127.0.0.1:8080/scan/datasources#x",
            origin,
        )


@pytest.mark.parametrize(
    "link",
    [
        "https://account.purview.azure.com:abc/scan/datasources",
        "https://account.purview.azure.com:99999/scan/datasources",
        "https://[::1/scan/datasources",
    ],
)
def test_next_link_invalid_port_or_brackets_is_pagination_error(link: str) -> None:
    origin = EndpointOrigin("https", "account.purview.azure.com", None)
    with pytest.raises(PurviewPaginationError) as exc_info:
        validate_absolute_same_origin_next_link(link, origin)
    error = exc_info.value
    assert error.code == "scanning.invalid_pagination_link"
    assert error.__cause__ is None
    assert error.__context__ is None
    assert not isinstance(error, ValueError)
    # Public message must not echo the raw nextLink.
    assert link not in error.message
    assert ":abc" not in error.message
    assert "99999" not in error.message
