"""Shared AzureStorage Data Source endpoint safety policy tests."""

from __future__ import annotations

import traceback

import pytest

from purview_governance.data_source_endpoint import (
    DataSourceEndpointError,
    validate_data_source_endpoint,
)

SENTINEL = "SECRET_ENDPOINT_SENTINEL_7f91"


def _assert_sanitized(exc: BaseException) -> None:
    assert SENTINEL not in str(exc)
    assert SENTINEL not in repr(exc)
    rendered = "".join(traceback.format_exception(exc))
    assert SENTINEL not in rendered
    assert getattr(exc, "__cause__", "missing") is None
    assert getattr(exc, "__context__", "missing") is None
    for attr in vars(exc).values():
        if isinstance(attr, str):
            assert SENTINEL not in attr


@pytest.mark.parametrize(
    "raw",
    [
        f"https://user:{SENTINEL}@example.blob.core.windows.net/",
        f"https://example.blob.core.windows.net/?sv=1&sig={SENTINEL}",
        f"https://example.blob.core.windows.net/#{SENTINEL}",
        "http://example.blob.core.windows.net/",
        "https:///path-only",
        "https://[::1",
        "https://example.blob.core.windows.net:notaport/",
    ],
)
def test_unsafe_endpoints_rejected_without_echo(raw: str) -> None:
    with pytest.raises(DataSourceEndpointError) as exc_info:
        validate_data_source_endpoint(raw)
    assert exc_info.value.code == "data_source_endpoint.invalid"
    _assert_sanitized(exc_info.value)


def test_valid_endpoint_preserves_strip_only_semantics() -> None:
    raw = "  https://example.blob.core.windows.net/container/  "
    validated = validate_data_source_endpoint(raw)
    assert validated == "https://example.blob.core.windows.net/container/"
    # Trailing slash and path preserved; no host lowercasing rewrite beyond input.
    exact = "https://Example.Blob.Core.Windows.Net/"
    assert validate_data_source_endpoint(exact) == exact
