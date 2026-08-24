"""Microsoft Purview Unified Catalog Public Preview HTTP client foundation."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode, urlsplit

import httpx

from purview_governance.auth.provider import PurviewAuthorizationProvider
from purview_governance.unified_catalog.constants import (
    BUSINESS_DOMAINS_PATH,
    DATA_PRODUCTS_PATH,
    DEFAULT_TIMEOUT,
    GLOSSARY_TERMS_PATH,
    MAX_LIST_PAGES,
    UNIFIED_CATALOG_API_VERSION,
    UNIFIED_CATALOG_PRODUCTION_ENDPOINT,
)
from purview_governance.unified_catalog.endpoint import normalize_unified_catalog_endpoint
from purview_governance.unified_catalog.errors import (
    UnifiedCatalogHttpError,
    UnifiedCatalogPaginationError,
    UnifiedCatalogRequestError,
    UnifiedCatalogResponseError,
    UnifiedCatalogTimeoutError,
)
from purview_governance.unified_catalog.origin import (
    EndpointOrigin,
    origin_from_https_endpoint,
    origin_from_loopback_http_base_url,
    validate_absolute_same_origin_next_link,
)


@dataclass(frozen=True, slots=True)
class BusinessDomainListResult:
    """Aggregated Business Domain enumerate snapshot (defensive copies of ``value`` items)."""

    items: tuple[dict[str, Any], ...]

    @property
    def item_count(self) -> int:
        return len(self.items)


@dataclass(frozen=True, slots=True)
class DataProductListResult:
    """Aggregated Data Product enumerate snapshot (defensive copies of ``value`` items)."""

    items: tuple[dict[str, Any], ...]

    @property
    def item_count(self) -> int:
        return len(self.items)


@dataclass(frozen=True, slots=True)
class GlossaryTermListResult:
    """Aggregated Glossary Term enumerate snapshot (defensive copies of ``value`` items)."""

    items: tuple[dict[str, Any], ...]

    @property
    def item_count(self) -> int:
        return len(self.items)


def _defensive_snapshot(value: Any) -> Any:
    return copy.deepcopy(value)


def _parse_json_object(response: httpx.Response, *, operation: str) -> dict[str, Any]:
    parse_failed = False
    try:
        data = response.json()
    except (json.JSONDecodeError, ValueError):
        parse_failed = True
    if parse_failed:
        raise UnifiedCatalogResponseError(
            "unified_catalog.invalid_json_response",
            f"{operation} response is not valid JSON",
        )
    if not isinstance(data, dict):
        raise UnifiedCatalogResponseError(
            "unified_catalog.invalid_response_contract",
            f"{operation} response must be a JSON object",
        )
    return data


def _validate_paged_domain_page(data: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    if "value" not in data:
        raise UnifiedCatalogResponseError(
            "unified_catalog.invalid_response_contract",
            "PagedDomain response must include a value array",
        )
    value = data["value"]
    if not isinstance(value, list):
        raise UnifiedCatalogResponseError(
            "unified_catalog.invalid_response_contract",
            "PagedDomain value must be an array",
        )
    items: list[dict[str, Any]] = []
    for entry in value:
        if not isinstance(entry, dict):
            raise UnifiedCatalogResponseError(
                "unified_catalog.invalid_response_contract",
                "PagedDomain value entries must be JSON objects",
            )
        items.append(_defensive_snapshot(entry))

    next_link: str | None = None
    if "nextLink" in data and data["nextLink"] is not None:
        raw = data["nextLink"]
        if not isinstance(raw, str) or not raw.strip():
            raise UnifiedCatalogResponseError(
                "unified_catalog.invalid_response_contract",
                "PagedDomain nextLink must be a non-empty string when present",
            )
        next_link = raw.strip()
    return items, next_link


def _validate_paged_data_product_page(
    data: dict[str, Any],
) -> tuple[list[dict[str, Any]], str | None]:
    if "value" not in data:
        raise UnifiedCatalogResponseError(
            "unified_catalog.invalid_response_contract",
            "PagedDataProduct response must include a value array",
        )
    value = data["value"]
    if not isinstance(value, list):
        raise UnifiedCatalogResponseError(
            "unified_catalog.invalid_response_contract",
            "PagedDataProduct value must be an array",
        )
    items: list[dict[str, Any]] = []
    for entry in value:
        if not isinstance(entry, dict):
            raise UnifiedCatalogResponseError(
                "unified_catalog.invalid_response_contract",
                "PagedDataProduct value entries must be JSON objects",
            )
        items.append(_defensive_snapshot(entry))

    next_link: str | None = None
    if "nextLink" in data and data["nextLink"] is not None:
        raw = data["nextLink"]
        if not isinstance(raw, str) or not raw.strip():
            raise UnifiedCatalogResponseError(
                "unified_catalog.invalid_response_contract",
                "PagedDataProduct nextLink must be a non-empty string when present",
            )
        next_link = raw.strip()
    return items, next_link


def _validate_paged_term_page(
    data: dict[str, Any],
) -> tuple[list[dict[str, Any]], str | None]:
    if "value" not in data:
        raise UnifiedCatalogResponseError(
            "unified_catalog.invalid_response_contract",
            "PagedTerm response must include a value array",
        )
    value = data["value"]
    if not isinstance(value, list):
        raise UnifiedCatalogResponseError(
            "unified_catalog.invalid_response_contract",
            "PagedTerm value must be an array",
        )
    items: list[dict[str, Any]] = []
    for entry in value:
        if not isinstance(entry, dict):
            raise UnifiedCatalogResponseError(
                "unified_catalog.invalid_response_contract",
                "PagedTerm value entries must be JSON objects",
            )
        items.append(_defensive_snapshot(entry))

    next_link: str | None = None
    if "nextLink" in data and data["nextLink"] is not None:
        raw = data["nextLink"]
        if not isinstance(raw, str) or not raw.strip():
            raise UnifiedCatalogResponseError(
                "unified_catalog.invalid_response_contract",
                "PagedTerm nextLink must be a non-empty string when present",
            )
        next_link = raw.strip()
    return items, next_link


class PurviewUnifiedCatalogClient:
    """Bounded Unified Catalog client for Business Domain read (Public Preview)."""

    def __init__(
        self,
        endpoint: str,
        auth_provider: PurviewAuthorizationProvider,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        normalized = normalize_unified_catalog_endpoint(endpoint)
        origin = origin_from_https_endpoint(normalized)
        self._configure(
            origin,
            auth_provider,
            transport=transport,
            trust_env=True,
            logical_target_endpoint=normalized,
        )

    def _configure(
        self,
        origin: EndpointOrigin,
        auth_provider: PurviewAuthorizationProvider,
        *,
        transport: httpx.BaseTransport | None,
        trust_env: bool,
        logical_target_endpoint: str,
    ) -> None:
        self._auth_provider = auth_provider
        self._origin = origin
        self._base_url = origin.canonical_base_url
        self._logical_target_endpoint = logical_target_endpoint
        self._http = httpx.Client(
            transport=transport,
            timeout=DEFAULT_TIMEOUT,
            follow_redirects=False,
            trust_env=trust_env,
        )
        self._closed = False

    @classmethod
    def _from_loopback_base_url(
        cls,
        base_url: str,
        auth_provider: PurviewAuthorizationProvider,
        *,
        logical_target_endpoint: str = UNIFIED_CATALOG_PRODUCTION_ENDPOINT,
        transport: httpx.BaseTransport | None = None,
    ) -> PurviewUnifiedCatalogClient:
        """Package-private loopback HTTP seam (literal loopback IP only).

        Not exported from ``unified_catalog.__all__``. Used by offline contract tests.
        """
        origin = origin_from_loopback_http_base_url(base_url)
        client = cls.__new__(cls)
        client._configure(
            origin,
            auth_provider,
            transport=transport,
            trust_env=False,
            logical_target_endpoint=logical_target_endpoint,
        )
        return client

    def __enter__(self) -> PurviewUnifiedCatalogClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        if not self._closed:
            self._http.close()
            self._closed = True

    @property
    def follow_redirects(self) -> bool:
        return bool(self._http.follow_redirects)

    @property
    def timeout(self) -> httpx.Timeout:
        return self._http.timeout

    @property
    def trust_env(self) -> bool:
        return bool(self._http.trust_env)

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def target_endpoint(self) -> str:
        """Logical HTTPS Unified Catalog target (not transport origin)."""
        return self._logical_target_endpoint

    def _authorization_header(self) -> str:
        return self._auth_provider.acquire_authorization_header()

    def _business_domains_url(self) -> str:
        query = urlencode({"api-version": UNIFIED_CATALOG_API_VERSION})
        return f"{self._base_url}{BUSINESS_DOMAINS_PATH}?{query}"

    def _data_products_url(self) -> str:
        query = urlencode({"api-version": UNIFIED_CATALOG_API_VERSION})
        return f"{self._base_url}{DATA_PRODUCTS_PATH}?{query}"

    def _glossary_terms_url(self) -> str:
        query = urlencode({"api-version": UNIFIED_CATALOG_API_VERSION})
        return f"{self._base_url}{GLOSSARY_TERMS_PATH}?{query}"

    def _safe_path(self, url: str) -> str:
        parts = urlsplit(url)
        return parts.path or "/"

    def _raise_http_error(
        self,
        response: httpx.Response,
        *,
        operation: str,
        method: str,
        url: str,
    ) -> None:
        raise UnifiedCatalogHttpError(
            "unified_catalog.http_error",
            f"{operation} failed with unexpected HTTP status",
            status_code=response.status_code,
            method=method,
            path=self._safe_path(url),
        )

    def _send(
        self,
        method: str,
        url: str,
        *,
        operation: str,
        headers: dict[str, str],
    ) -> httpx.Response:
        failed_timeout = False
        failed_request = False
        try:
            return self._http.request(
                method,
                url,
                headers=headers,
                follow_redirects=False,
                timeout=DEFAULT_TIMEOUT,
            )
        except httpx.TimeoutException:
            failed_timeout = True
        except httpx.RequestError:
            failed_request = True
        if failed_timeout:
            raise UnifiedCatalogTimeoutError(
                "unified_catalog.timeout",
                f"{operation} timed out",
            )
        if failed_request:
            raise UnifiedCatalogRequestError(
                "unified_catalog.request_failed",
                f"{operation} transport request failed",
            )
        raise AssertionError("unreachable")

    def _enumerate_business_domains_paginated(self) -> tuple[dict[str, Any], ...]:
        url = self._business_domains_url()
        aggregated: list[dict[str, Any]] = []
        seen_links: set[str] = set()
        pages = 0

        while True:
            pages += 1
            if pages > MAX_LIST_PAGES:
                raise UnifiedCatalogPaginationError(
                    "unified_catalog.pagination_limit_exceeded",
                    "business domain pagination exceeded the maximum number of pages",
                )

            headers = {
                "Authorization": self._authorization_header(),
                "Accept": "application/json",
            }
            response = self._send(
                "GET",
                url,
                operation="enumerate_business_domains",
                headers=headers,
            )
            if response.status_code != 200:
                self._raise_http_error(
                    response,
                    operation="enumerate_business_domains",
                    method="GET",
                    url=url,
                )

            data = _parse_json_object(response, operation="enumerate_business_domains")
            items, next_link = _validate_paged_domain_page(data)
            aggregated.extend(items)

            if next_link is None:
                break
            if next_link in seen_links:
                raise UnifiedCatalogPaginationError(
                    "unified_catalog.pagination_loop",
                    "business domain pagination encountered a repeated nextLink",
                )
            seen_links.add(next_link)
            url = validate_absolute_same_origin_next_link(next_link, self._origin)

        return tuple(aggregated)

    def enumerate_business_domains(self) -> BusinessDomainListResult:
        """Enumerate Business Domains (PagedDomain), following same-origin ``nextLink`` values."""
        return BusinessDomainListResult(items=self._enumerate_business_domains_paginated())

    def _enumerate_data_products_paginated(self) -> tuple[dict[str, Any], ...]:
        url = self._data_products_url()
        aggregated: list[dict[str, Any]] = []
        seen_links: set[str] = set()
        pages = 0

        while True:
            pages += 1
            if pages > MAX_LIST_PAGES:
                raise UnifiedCatalogPaginationError(
                    "unified_catalog.pagination_limit_exceeded",
                    "data product pagination exceeded the maximum number of pages",
                )

            headers = {
                "Authorization": self._authorization_header(),
                "Accept": "application/json",
            }
            response = self._send(
                "GET",
                url,
                operation="enumerate_data_products",
                headers=headers,
            )
            if response.status_code != 200:
                self._raise_http_error(
                    response,
                    operation="enumerate_data_products",
                    method="GET",
                    url=url,
                )

            data = _parse_json_object(response, operation="enumerate_data_products")
            items, next_link = _validate_paged_data_product_page(data)
            aggregated.extend(items)

            if next_link is None:
                break
            if next_link in seen_links:
                raise UnifiedCatalogPaginationError(
                    "unified_catalog.pagination_loop",
                    "data product pagination encountered a repeated nextLink",
                )
            seen_links.add(next_link)
            url = validate_absolute_same_origin_next_link(next_link, self._origin)

        return tuple(aggregated)

    def enumerate_data_products(self) -> DataProductListResult:
        """Enumerate Data Products (PagedDataProduct), following same-origin ``nextLink`` values."""
        return DataProductListResult(items=self._enumerate_data_products_paginated())

    def _enumerate_glossary_terms_paginated(self) -> tuple[dict[str, Any], ...]:
        url = self._glossary_terms_url()
        aggregated: list[dict[str, Any]] = []
        seen_links: set[str] = set()
        pages = 0

        while True:
            pages += 1
            if pages > MAX_LIST_PAGES:
                raise UnifiedCatalogPaginationError(
                    "unified_catalog.pagination_limit_exceeded",
                    "glossary term pagination exceeded the maximum number of pages",
                )

            headers = {
                "Authorization": self._authorization_header(),
                "Accept": "application/json",
            }
            response = self._send(
                "GET",
                url,
                operation="enumerate_glossary_terms",
                headers=headers,
            )
            if response.status_code != 200:
                self._raise_http_error(
                    response,
                    operation="enumerate_glossary_terms",
                    method="GET",
                    url=url,
                )

            data = _parse_json_object(response, operation="enumerate_glossary_terms")
            items, next_link = _validate_paged_term_page(data)
            aggregated.extend(items)

            if next_link is None:
                break
            if next_link in seen_links:
                raise UnifiedCatalogPaginationError(
                    "unified_catalog.pagination_loop",
                    "glossary term pagination encountered a repeated nextLink",
                )
            seen_links.add(next_link)
            url = validate_absolute_same_origin_next_link(next_link, self._origin)

        return tuple(aggregated)

    def enumerate_glossary_terms(self) -> GlossaryTermListResult:
        """Enumerate Glossary Terms (PagedTerm), following same-origin ``nextLink`` values."""
        return GlossaryTermListResult(items=self._enumerate_glossary_terms_paginated())
