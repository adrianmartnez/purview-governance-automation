"""Canonical endpoint origin helpers for Unified Catalog client and nextLink checks."""

from __future__ import annotations

import contextlib
import ipaddress
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from purview_governance.unified_catalog.errors import (
    UnifiedCatalogPaginationError,
    UnifiedCatalogRequestBuildError,
)


@dataclass(frozen=True, slots=True)
class EndpointOrigin:
    """Scheme + host + effective port used for same-origin comparisons."""

    scheme: str
    host: str
    port: int | None

    @property
    def effective_port(self) -> int:
        if self.port is not None:
            return self.port
        if self.scheme == "https":
            return 443
        if self.scheme == "http":
            return 80
        raise UnifiedCatalogRequestBuildError(
            "unified_catalog.invalid_endpoint",
            "unsupported endpoint scheme",
        )

    @property
    def origin_key(self) -> tuple[str, str, int]:
        return (self.scheme, self.host, self.effective_port)

    @property
    def netloc(self) -> str:
        try:
            ip = ipaddress.ip_address(self.host)
        except ValueError:
            ip = None
        host_part = f"[{self.host}]" if ip is not None and ip.version == 6 else self.host
        if self.port is None:
            return host_part
        return f"{host_part}:{self.port}"

    @property
    def canonical_base_url(self) -> str:
        return urlunsplit((self.scheme, self.netloc, "", "", ""))


def origin_from_https_endpoint(endpoint: str) -> EndpointOrigin:
    """Build origin from a normalized HTTPS Unified Catalog endpoint."""
    parse_failed = False
    try:
        parts = urlsplit(endpoint)
        host = parts.hostname
        port = parts.port
        scheme = parts.scheme.lower()
    except ValueError:
        parse_failed = True
    if parse_failed:
        raise UnifiedCatalogRequestBuildError(
            "unified_catalog.invalid_endpoint",
            "endpoint is not a valid https URL",
        )
    if scheme != "https":
        raise UnifiedCatalogRequestBuildError(
            "unified_catalog.invalid_endpoint",
            "endpoint must use https",
        )
    if not host:
        raise UnifiedCatalogRequestBuildError(
            "unified_catalog.invalid_endpoint",
            "endpoint must include a hostname",
        )
    return EndpointOrigin(scheme="https", host=host.lower(), port=port)


def origin_from_loopback_http_base_url(base_url: str) -> EndpointOrigin:
    """Package-private seam: HTTP only for literal loopback IP addresses."""
    parse_failed = False
    try:
        parts = urlsplit(base_url.strip())
        host = parts.hostname
        port = parts.port
        scheme = parts.scheme.lower()
        username = parts.username
        password = parts.password
        query = parts.query
        fragment = parts.fragment
        path_part = parts.path or ""
    except ValueError:
        parse_failed = True
    if parse_failed:
        raise UnifiedCatalogRequestBuildError(
            "unified_catalog.invalid_endpoint",
            "loopback endpoint is not a valid URL",
        )

    if scheme != "http":
        raise UnifiedCatalogRequestBuildError(
            "unified_catalog.invalid_endpoint",
            "loopback endpoint must use http",
        )
    if not host:
        raise UnifiedCatalogRequestBuildError(
            "unified_catalog.invalid_endpoint",
            "loopback endpoint must include a hostname",
        )
    if username is not None or password is not None:
        raise UnifiedCatalogRequestBuildError(
            "unified_catalog.invalid_endpoint",
            "loopback endpoint must not include userinfo",
        )
    if query:
        raise UnifiedCatalogRequestBuildError(
            "unified_catalog.invalid_endpoint",
            "loopback endpoint must not include a query string",
        )
    if fragment:
        raise UnifiedCatalogRequestBuildError(
            "unified_catalog.invalid_endpoint",
            "loopback endpoint must not include a fragment",
        )
    if path_part not in {"", "/"}:
        raise UnifiedCatalogRequestBuildError(
            "unified_catalog.invalid_endpoint",
            "loopback endpoint must not include a path",
        )

    ip_failed = False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip_failed = True
    if ip_failed:
        raise UnifiedCatalogRequestBuildError(
            "unified_catalog.invalid_endpoint",
            "loopback endpoint host must be a literal loopback IP address",
        )
    if not ip.is_loopback:
        raise UnifiedCatalogRequestBuildError(
            "unified_catalog.invalid_endpoint",
            "loopback endpoint host must be a loopback IP address",
        )

    return EndpointOrigin(scheme="http", host=str(ip), port=port)


def validate_absolute_same_origin_next_link(
    next_link: str,
    expected: EndpointOrigin,
) -> str:
    """Validate ``nextLink`` before any follow request."""
    if not isinstance(next_link, str) or not next_link.strip():
        raise UnifiedCatalogPaginationError(
            "unified_catalog.invalid_pagination_link",
            "nextLink must be a non-empty string",
        )
    raw = next_link.strip()
    parse_failed = False
    try:
        parts = urlsplit(raw)
        host = parts.hostname
        port = parts.port
        scheme = parts.scheme
        netloc = parts.netloc
        username = parts.username
        password = parts.password
        fragment = parts.fragment
    except ValueError:
        parse_failed = True
    if parse_failed:
        raise UnifiedCatalogPaginationError(
            "unified_catalog.invalid_pagination_link",
            "nextLink is not a valid URL",
        )

    if not scheme or not netloc:
        raise UnifiedCatalogPaginationError(
            "unified_catalog.invalid_pagination_link",
            "nextLink must be an absolute URL",
        )
    if username is not None or password is not None:
        raise UnifiedCatalogPaginationError(
            "unified_catalog.invalid_pagination_link",
            "nextLink must not include userinfo",
        )
    if fragment:
        raise UnifiedCatalogPaginationError(
            "unified_catalog.invalid_pagination_link",
            "nextLink must not include a fragment",
        )
    if not host:
        raise UnifiedCatalogPaginationError(
            "unified_catalog.invalid_pagination_link",
            "nextLink must include a hostname",
        )

    link_origin = EndpointOrigin(
        scheme=scheme.lower(),
        host=host.lower(),
        port=port,
    )
    with contextlib.suppress(ValueError):
        link_origin = EndpointOrigin(
            scheme=link_origin.scheme,
            host=str(ipaddress.ip_address(link_origin.host)),
            port=link_origin.port,
        )

    expected_compare = expected
    with contextlib.suppress(ValueError):
        expected_compare = EndpointOrigin(
            scheme=expected.scheme,
            host=str(ipaddress.ip_address(expected.host)),
            port=expected.port,
        )

    if link_origin.origin_key != expected_compare.origin_key:
        raise UnifiedCatalogPaginationError(
            "unified_catalog.invalid_pagination_link",
            "nextLink origin does not match the configured endpoint origin",
        )
    return raw
