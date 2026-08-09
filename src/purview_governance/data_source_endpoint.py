"""Project safety policy for AzureStorage Data Source material endpoints.

Microsoft Purview Scanning ``2023-09-01`` documents AzureStorage ``endpoint`` as a
string. This module applies a stricter offline project policy so credential-bearing
URLs (userinfo / query / fragment) cannot enter remote-state artifacts or diff
before/after values. It does not claim Microsoft marks the field ``format: uri``.
"""

from __future__ import annotations

from urllib.parse import urlsplit


class DataSourceEndpointError(Exception):
    """Sanitized Data Source endpoint validation failure (never includes raw URL)."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")

    def __repr__(self) -> str:
        return f"DataSourceEndpointError(code={self.code!r}, message={self.message!r})"


_FIXED_MESSAGE = "Data Source endpoint is invalid or unsafe"


def validate_data_source_endpoint(raw: object) -> str:
    """Validate a material Data Source endpoint; return stripped original text.

    Rules (project safety policy):
    - must be a ``str``;
    - outer ``strip()`` only;
    - non-empty after strip;
    - parse with ``urllib.parse.urlsplit`` (offline, no DNS);
    - scheme must be HTTPS (case-insensitive scheme token ``https``);
    - hostname required;
    - reject username/password userinfo;
    - reject any query string;
    - reject any fragment;
    - do **not** reconstruct/canonicalize the URL (trailing slash / path / casing
      preserved exactly as in the stripped input).
    """
    if not isinstance(raw, str):
        raise DataSourceEndpointError(
            "data_source_endpoint.invalid",
            _FIXED_MESSAGE,
        )

    endpoint = raw.strip()
    if not endpoint:
        raise DataSourceEndpointError(
            "data_source_endpoint.invalid",
            _FIXED_MESSAGE,
        )

    parse_failed = False
    try:
        parts = urlsplit(endpoint)
        # Access hostname/port inside try: malformed brackets/ports raise ValueError.
        hostname = parts.hostname
        _ = parts.port
    except ValueError:
        parse_failed = True
    if parse_failed:
        raise DataSourceEndpointError(
            "data_source_endpoint.invalid",
            _FIXED_MESSAGE,
        ) from None

    if parts.scheme.lower() != "https":
        raise DataSourceEndpointError(
            "data_source_endpoint.invalid",
            _FIXED_MESSAGE,
        )
    if not hostname:
        raise DataSourceEndpointError(
            "data_source_endpoint.invalid",
            _FIXED_MESSAGE,
        )
    if parts.username is not None or parts.password is not None:
        raise DataSourceEndpointError(
            "data_source_endpoint.invalid",
            _FIXED_MESSAGE,
        )
    if parts.query:
        raise DataSourceEndpointError(
            "data_source_endpoint.invalid",
            _FIXED_MESSAGE,
        )
    if parts.fragment:
        raise DataSourceEndpointError(
            "data_source_endpoint.invalid",
            _FIXED_MESSAGE,
        )

    # Return stripped original — never a reconstructed URL.
    return endpoint
