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
    DATA_ASSETS_PATH,
    DATA_COLUMN_QUERY_PAGE_SIZE,
    DATA_COLUMNS_QUERY_PATH,
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


@dataclass(frozen=True, slots=True)
class DataAssetListResult:
    """Aggregated Data Asset enumerate snapshot."""

    items: tuple[dict[str, Any], ...]

    @property
    def item_count(self) -> int:
        return len(self.items)


@dataclass(frozen=True, slots=True)
class DataColumnQueryResult:
    """Aggregated Data Column query snapshot."""

    items: tuple[dict[str, Any], ...]

    @property
    def item_count(self) -> int:
        return len(self.items)


@dataclass(frozen=True, slots=True)
class GovernanceRelationshipListResult:
    """Aggregated governance relationship list snapshot."""

    items: tuple[dict[str, Any], ...]

    @property
    def item_count(self) -> int:
        return len(self.items)


def _validate_paged_value_page(
    data: dict[str, Any],
    *,
    contract_name: str,
) -> tuple[list[dict[str, Any]], str | None]:
    if "value" not in data:
        raise UnifiedCatalogResponseError(
            "unified_catalog.invalid_response_contract",
            f"{contract_name} response must include a value array",
        )
    value = data["value"]
    if not isinstance(value, list):
        raise UnifiedCatalogResponseError(
            "unified_catalog.invalid_response_contract",
            f"{contract_name} value must be an array",
        )
    items: list[dict[str, Any]] = []
    for entry in value:
        if not isinstance(entry, dict):
            raise UnifiedCatalogResponseError(
                "unified_catalog.invalid_response_contract",
                f"{contract_name} value entries must be JSON objects",
            )
        items.append(_defensive_snapshot(entry))

    next_link: str | None = None
    if "nextLink" in data and data["nextLink"] is not None:
        raw = data["nextLink"]
        if not isinstance(raw, str) or not raw.strip():
            raise UnifiedCatalogResponseError(
                "unified_catalog.invalid_response_contract",
                f"{contract_name} nextLink must be a non-empty string when present",
            )
        next_link = raw.strip()
    return items, next_link


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
        json_body: dict[str, Any] | None = None,
    ) -> httpx.Response:
        failed_timeout = False
        failed_request = False
        try:
            return self._http.request(
                method,
                url,
                headers=headers,
                json=json_body,
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

    def _paginate_get_list(
        self,
        initial_url: str,
        *,
        operation: str,
        contract_name: str,
    ) -> tuple[dict[str, Any], ...]:
        url = initial_url
        aggregated: list[dict[str, Any]] = []
        seen_links: set[str] = set()
        pages = 0

        while True:
            pages += 1
            if pages > MAX_LIST_PAGES:
                raise UnifiedCatalogPaginationError(
                    "unified_catalog.pagination_limit_exceeded",
                    f"{operation} pagination exceeded the maximum number of pages",
                )

            headers = {
                "Authorization": self._authorization_header(),
                "Accept": "application/json",
            }
            response = self._send(
                "GET",
                url,
                operation=operation,
                headers=headers,
            )
            if response.status_code != 200:
                self._raise_http_error(
                    response,
                    operation=operation,
                    method="GET",
                    url=url,
                )

            data = _parse_json_object(response, operation=operation)
            items, next_link = _validate_paged_value_page(data, contract_name=contract_name)
            aggregated.extend(items)

            if next_link is None:
                break
            if next_link in seen_links:
                raise UnifiedCatalogPaginationError(
                    "unified_catalog.pagination_loop",
                    f"{operation} pagination encountered a repeated nextLink",
                )
            seen_links.add(next_link)
            url = validate_absolute_same_origin_next_link(next_link, self._origin)

        return tuple(aggregated)

    def _data_assets_url(self) -> str:
        query = urlencode(
            {
                "api-version": UNIFIED_CATALOG_API_VERSION,
                "includeExtendedProperties": "false",
            }
        )
        return f"{self._base_url}{DATA_ASSETS_PATH}?{query}"

    def _data_product_relationships_url(self, product_id: str, entity_type: str) -> str:
        query = urlencode(
            {
                "api-version": UNIFIED_CATALOG_API_VERSION,
                "entityType": entity_type,
            }
        )
        return f"{self._base_url}{DATA_PRODUCTS_PATH}/{product_id}/relationships?{query}"

    def _glossary_term_relationships_url(
        self,
        term_id: str,
        entity_type: str,
        relationship_type: str,
    ) -> str:
        query = urlencode(
            {
                "api-version": UNIFIED_CATALOG_API_VERSION,
                "entityType": entity_type,
                "relationshipType": relationship_type,
            }
        )
        return f"{self._base_url}{GLOSSARY_TERMS_PATH}/{term_id}/relationships?{query}"

    def enumerate_data_assets(self) -> DataAssetListResult:
        """Enumerate Data Assets without extended properties."""
        return DataAssetListResult(
            items=self._paginate_get_list(
                self._data_assets_url(),
                operation="enumerate_data_assets",
                contract_name="PagedDataAsset",
            )
        )

    def query_data_columns(self) -> DataColumnQueryResult:
        """Query Data Columns with orphan and enrichment flags (POST pagination §10)."""
        aggregated: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        current_offset = 0
        pages = 0
        query_url = (
            f"{self._base_url}{DATA_COLUMNS_QUERY_PATH}"
            f"?{urlencode({'api-version': UNIFIED_CATALOG_API_VERSION})}"
        )

        while True:
            pages += 1
            if pages > MAX_LIST_PAGES:
                raise UnifiedCatalogPaginationError(
                    "unified_catalog.pagination_limit_exceeded",
                    "data column query pagination exceeded the maximum number of pages",
                )

            body = {
                "includingOrphans": True,
                "includeColumnDetails": True,
                "includeAssetDetails": True,
                "skip": current_offset,
                "top": DATA_COLUMN_QUERY_PAGE_SIZE,
            }
            headers = {
                "Authorization": self._authorization_header(),
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
            response = self._send(
                "POST",
                query_url,
                operation="query_data_columns",
                headers=headers,
                json_body=body,
            )
            if response.status_code != 200:
                self._raise_http_error(
                    response,
                    operation="query_data_columns",
                    method="POST",
                    url=query_url,
                )

            data = _parse_json_object(response, operation="query_data_columns")
            items, next_link = _validate_paged_value_page(
                data,
                contract_name="DataColumnQueryResponse",
            )
            if next_link is not None:
                validate_absolute_same_origin_next_link(next_link, self._origin)

            if len(items) == 0:
                if next_link is not None:
                    raise UnifiedCatalogPaginationError(
                        "unified_catalog.invalid_pagination_link",
                        "empty data column page must not include nextLink",
                    )
                break

            for item in items:
                raw_id = item.get("id")
                if not isinstance(raw_id, str):
                    raise UnifiedCatalogResponseError(
                        "unified_catalog.invalid_response_contract",
                        "data column id must be a string",
                    )
                if raw_id in seen_ids:
                    raise UnifiedCatalogPaginationError(
                        "unified_catalog.duplicate_id",
                        "duplicate data column id across query pages",
                    )
                seen_ids.add(raw_id)
            aggregated.extend(items)

            if next_link is not None:
                current_offset += len(items)
                continue

            if len(items) < DATA_COLUMN_QUERY_PAGE_SIZE:
                break
            current_offset += len(items)

        return DataColumnQueryResult(items=tuple(aggregated))

    def list_data_product_relationships(
        self,
        product_id: str,
        *,
        entity_type: str = "DATAASSET",
    ) -> GovernanceRelationshipListResult:
        """List Data Product relationships for one product (family A)."""
        url = self._data_product_relationships_url(product_id, entity_type)
        return GovernanceRelationshipListResult(
            items=self._paginate_get_list(
                url,
                operation="list_data_product_relationships",
                contract_name="PagedDataProductRelationship",
            )
        )

    def list_glossary_term_relationships(
        self,
        term_id: str,
        *,
        entity_type: str,
        relationship_type: str = "Related",
    ) -> GovernanceRelationshipListResult:
        """List Glossary Term relationships for one term (families B/C)."""
        url = self._glossary_term_relationships_url(term_id, entity_type, relationship_type)
        return GovernanceRelationshipListResult(
            items=self._paginate_get_list(
                url,
                operation="list_glossary_term_relationships",
                contract_name="PagedTermRelationship",
            )
        )

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

    def _require_tenant_bound_execution_context(self):
        """APPLY/v3 execution boundary: tenant-aware provider required."""
        from purview_governance.auth.tenant_bound import (
            TenantBindingUnsupportedError,
            is_tenant_bound_provider,
        )

        if not is_tenant_bound_provider(self._auth_provider):
            raise TenantBindingUnsupportedError(
                "apply.tenant_binding_unsupported",
                "APPLY/v3 requires a tenant-bound authorization provider",
            )
        return self._auth_provider.execution_context()

    def get_business_domain(self, domain_id: str) -> dict[str, Any]:
        """Targeted GET for one Business Domain."""
        query = urlencode({"api-version": UNIFIED_CATALOG_API_VERSION})
        url = f"{self._base_url}{BUSINESS_DOMAINS_PATH}/{domain_id}?{query}"
        headers = {
            "Authorization": self._authorization_header(),
            "Accept": "application/json",
        }
        response = self._send(
            "GET",
            url,
            operation="get_business_domain",
            headers=headers,
        )
        if response.status_code == 404:
            self._raise_http_error(
                response,
                operation="get_business_domain",
                method="GET",
                url=url,
            )
        if response.status_code != 200:
            self._raise_http_error(
                response,
                operation="get_business_domain",
                method="GET",
                url=url,
            )
        return _defensive_snapshot(_parse_json_object(response, operation="get_business_domain"))

    def get_data_product(self, product_id: str) -> dict[str, Any]:
        """Targeted GET for one Data Product."""
        query = urlencode({"api-version": UNIFIED_CATALOG_API_VERSION})
        url = f"{self._base_url}{DATA_PRODUCTS_PATH}/{product_id}?{query}"
        headers = {
            "Authorization": self._authorization_header(),
            "Accept": "application/json",
        }
        response = self._send(
            "GET",
            url,
            operation="get_data_product",
            headers=headers,
        )
        if response.status_code == 404:
            self._raise_http_error(
                response,
                operation="get_data_product",
                method="GET",
                url=url,
            )
        if response.status_code != 200:
            self._raise_http_error(
                response,
                operation="get_data_product",
                method="GET",
                url=url,
            )
        return _defensive_snapshot(_parse_json_object(response, operation="get_data_product"))

    def get_glossary_term(self, term_id: str) -> dict[str, Any]:
        """Targeted GET for one Glossary Term."""
        query = urlencode({"api-version": UNIFIED_CATALOG_API_VERSION})
        url = f"{self._base_url}{GLOSSARY_TERMS_PATH}/{term_id}?{query}"
        headers = {
            "Authorization": self._authorization_header(),
            "Accept": "application/json",
        }
        response = self._send(
            "GET",
            url,
            operation="get_glossary_term",
            headers=headers,
        )
        if response.status_code == 404:
            self._raise_http_error(
                response,
                operation="get_glossary_term",
                method="GET",
                url=url,
            )
        if response.status_code != 200:
            self._raise_http_error(
                response,
                operation="get_glossary_term",
                method="GET",
                url=url,
            )
        return _defensive_snapshot(_parse_json_object(response, operation="get_glossary_term"))

    def _update_business_domain(
        self,
        domain_id: str,
        payload: dict[str, Any],
    ) -> UnifiedCatalogWriteReceipt:
        query = urlencode({"api-version": UNIFIED_CATALOG_API_VERSION})
        url = f"{self._base_url}{BUSINESS_DOMAINS_PATH}/{domain_id}?{query}"
        headers = {
            "Authorization": self._authorization_header(),
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        response = self._send(
            "PUT",
            url,
            operation="update_business_domain",
            headers=headers,
            json_body=payload,
        )
        if response.status_code != 200:
            self._raise_http_error(
                response,
                operation="update_business_domain",
                method="PUT",
                url=url,
            )
        return UnifiedCatalogWriteReceipt(
            resource_type="businessDomain",
            resource_id=domain_id,
            status_code=response.status_code,
        )

    def _create_data_product(self, payload: dict[str, Any]) -> UnifiedCatalogWriteReceipt:
        query = urlencode({"api-version": UNIFIED_CATALOG_API_VERSION})
        url = f"{self._base_url}{DATA_PRODUCTS_PATH}?{query}"
        headers = {
            "Authorization": self._authorization_header(),
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        response = self._send(
            "POST",
            url,
            operation="create_data_product",
            headers=headers,
            json_body=payload,
        )
        if response.status_code != 201:
            self._raise_http_error(
                response,
                operation="create_data_product",
                method="POST",
                url=url,
            )
        product_id = payload.get("id")
        if not isinstance(product_id, str):
            raise UnifiedCatalogResponseError(
                "unified_catalog.invalid_request_contract",
                "data product create payload must include id",
            )
        return UnifiedCatalogWriteReceipt(
            resource_type="dataProduct",
            resource_id=product_id,
            status_code=response.status_code,
        )

    def _update_data_product(
        self,
        product_id: str,
        payload: dict[str, Any],
    ) -> UnifiedCatalogWriteReceipt:
        query = urlencode({"api-version": UNIFIED_CATALOG_API_VERSION})
        url = f"{self._base_url}{DATA_PRODUCTS_PATH}/{product_id}?{query}"
        headers = {
            "Authorization": self._authorization_header(),
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        response = self._send(
            "PUT",
            url,
            operation="update_data_product",
            headers=headers,
            json_body=payload,
        )
        if response.status_code != 200:
            self._raise_http_error(
                response,
                operation="update_data_product",
                method="PUT",
                url=url,
            )
        return UnifiedCatalogWriteReceipt(
            resource_type="dataProduct",
            resource_id=product_id,
            status_code=response.status_code,
        )

    def _create_glossary_term(self, payload: dict[str, Any]) -> UnifiedCatalogWriteReceipt:
        query = urlencode({"api-version": UNIFIED_CATALOG_API_VERSION})
        url = f"{self._base_url}{GLOSSARY_TERMS_PATH}?{query}"
        headers = {
            "Authorization": self._authorization_header(),
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        response = self._send(
            "POST",
            url,
            operation="create_glossary_term",
            headers=headers,
            json_body=payload,
        )
        if response.status_code != 201:
            self._raise_http_error(
                response,
                operation="create_glossary_term",
                method="POST",
                url=url,
            )
        term_id = payload.get("id")
        if not isinstance(term_id, str):
            raise UnifiedCatalogResponseError(
                "unified_catalog.invalid_request_contract",
                "glossary term create payload must include id",
            )
        return UnifiedCatalogWriteReceipt(
            resource_type="glossaryTerm",
            resource_id=term_id,
            status_code=response.status_code,
        )

    def _update_glossary_term(
        self,
        term_id: str,
        payload: dict[str, Any],
    ) -> UnifiedCatalogWriteReceipt:
        query = urlencode({"api-version": UNIFIED_CATALOG_API_VERSION})
        url = f"{self._base_url}{GLOSSARY_TERMS_PATH}/{term_id}?{query}"
        headers = {
            "Authorization": self._authorization_header(),
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        response = self._send(
            "PUT",
            url,
            operation="update_glossary_term",
            headers=headers,
            json_body=payload,
        )
        if response.status_code != 200:
            self._raise_http_error(
                response,
                operation="update_glossary_term",
                method="PUT",
                url=url,
            )
        return UnifiedCatalogWriteReceipt(
            resource_type="glossaryTerm",
            resource_id=term_id,
            status_code=response.status_code,
        )


@dataclass(frozen=True, slots=True)
class UnifiedCatalogWriteReceipt:
    resource_type: str
    resource_id: str
    status_code: int
