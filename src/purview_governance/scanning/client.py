"""Microsoft Purview Scanning Data Plane HTTP client foundation."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode, urlsplit

import httpx

from purview_governance.auth.provider import PurviewAuthorizationProvider
from purview_governance.config.normalize import normalize_endpoint
from purview_governance.scanning.constants import (
    DEFAULT_TIMEOUT,
    MAX_LIST_PAGES,
    SCANNING_API_VERSION,
)
from purview_governance.scanning.errors import (
    PurviewHttpError,
    PurviewPaginationError,
    PurviewRequestBuildError,
    PurviewRequestError,
    PurviewResponseError,
    PurviewTimeoutError,
)
from purview_governance.scanning.names import validate_data_source_name
from purview_governance.scanning.origin import (
    EndpointOrigin,
    origin_from_https_endpoint,
    origin_from_loopback_http_base_url,
    validate_absolute_same_origin_next_link,
)

_DATA_SOURCES_PATH = "/scan/datasources"


@dataclass(frozen=True, slots=True)
class DataSourceListResult:
    """Aggregated Data Source list snapshot (defensive copies of ``value`` items).

    ``item_count`` is always ``len(items)`` from values actually received.
    Remote ``count`` fields are validated per page but never summed or used for
    pagination decisions.
    """

    items: tuple[dict[str, Any], ...]

    @property
    def item_count(self) -> int:
        return len(self.items)


@dataclass(frozen=True, slots=True)
class DataSourceWriteReceipt:
    """Package-private confirmed write receipt (HTTP 200/201; no response body)."""

    name: str
    status_code: int


def _defensive_snapshot(value: Any) -> Any:
    """Deep-copy JSON-plain structures returned to callers (not deep-immutable)."""
    return copy.deepcopy(value)


def _serialize_json_body(payload: Mapping[str, Any]) -> bytes:
    if not isinstance(payload, Mapping):
        raise PurviewRequestBuildError(
            "scanning.invalid_json_payload",
            "request body must be a JSON object mapping",
        )
    # Materialize to a plain dict for deterministic key ordering.
    materialize_failed = False
    try:
        as_dict = dict(payload)
    except Exception:
        # Do not retain the raw exception; raise only after leaving except.
        materialize_failed = True
    if materialize_failed:
        raise PurviewRequestBuildError(
            "scanning.invalid_json_payload",
            "request body must be a JSON object mapping",
        )

    serialize_failed = False
    try:
        return json.dumps(
            as_dict,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError):
        serialize_failed = True
    if serialize_failed:
        raise PurviewRequestBuildError(
            "scanning.invalid_json_payload",
            "request body is not strict JSON-serializable",
        )
    raise AssertionError("unreachable")


def _parse_json_object(response: httpx.Response, *, operation: str) -> dict[str, Any]:
    parse_failed = False
    try:
        data = response.json()
    except (json.JSONDecodeError, ValueError):
        # JSONDecodeError.doc may contain remote body; do not retain or re-raise it.
        parse_failed = True
    if parse_failed:
        raise PurviewResponseError(
            "scanning.invalid_json_response",
            f"{operation} response is not valid JSON",
        )
    if not isinstance(data, dict):
        raise PurviewResponseError(
            "scanning.invalid_response_contract",
            f"{operation} response must be a JSON object",
        )
    return data


def _validate_list_page(data: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    if "value" not in data:
        raise PurviewResponseError(
            "scanning.invalid_response_contract",
            "list response must include a value array",
        )
    value = data["value"]
    if not isinstance(value, list):
        raise PurviewResponseError(
            "scanning.invalid_response_contract",
            "list response value must be an array",
        )
    items: list[dict[str, Any]] = []
    for entry in value:
        if not isinstance(entry, dict):
            raise PurviewResponseError(
                "scanning.invalid_response_contract",
                "list response value entries must be JSON objects",
            )
        items.append(_defensive_snapshot(entry))

    if "count" in data and data["count"] is not None:
        count = data["count"]
        if isinstance(count, bool) or not isinstance(count, int):
            raise PurviewResponseError(
                "scanning.invalid_response_contract",
                "list response count must be an integer when present",
            )

    next_link: str | None = None
    if "nextLink" in data and data["nextLink"] is not None:
        raw = data["nextLink"]
        if not isinstance(raw, str) or not raw.strip():
            raise PurviewResponseError(
                "scanning.invalid_response_contract",
                "list response nextLink must be a non-empty string when present",
            )
        next_link = raw.strip()
    return items, next_link


class PurviewScanningClient:
    """Bounded Scanning Data Plane client for Data Source read + internal PUT."""

    def __init__(
        self,
        endpoint: str,
        auth_provider: PurviewAuthorizationProvider,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        normalized = normalize_endpoint(endpoint)
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
        logical_target_endpoint: str,
        transport: httpx.BaseTransport | None = None,
    ) -> PurviewScanningClient:
        """Package-private loopback HTTP seam (literal loopback IP only).

        Not exported from ``scanning.__all__``. Used by offline contract tests.
        Does not call the public constructor (which always requires HTTPS).
        ``logical_target_endpoint`` is the HTTPS Purview target used for apply
        target-context checks; transport remains loopback HTTP only.
        """
        normalized_logical = normalize_endpoint(logical_target_endpoint)
        origin = origin_from_loopback_http_base_url(base_url)
        client = cls.__new__(cls)
        client._configure(
            origin,
            auth_provider,
            transport=transport,
            trust_env=False,
            logical_target_endpoint=normalized_logical,
        )
        return client

    def __enter__(self) -> PurviewScanningClient:
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
        """Logical HTTPS Purview target bound to this client (not transport origin)."""
        return self._logical_target_endpoint

    def _authorization_header(self) -> str:
        return self._auth_provider.acquire_authorization_header()

    def _data_sources_url(self, name: str | None = None) -> str:
        path = _DATA_SOURCES_PATH if name is None else f"{_DATA_SOURCES_PATH}/{name}"
        query = urlencode({"api-version": SCANNING_API_VERSION})
        return f"{self._base_url}{path}?{query}"

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
        # PR3: do not copy arbitrary server x-ms-* metadata into public errors
        # (values could echo Authorization material). Telemetry can come later.
        raise PurviewHttpError(
            "scanning.http_error",
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
        content: bytes | None = None,
    ) -> httpx.Response:
        failed_timeout = False
        failed_request = False
        try:
            return self._http.request(
                method,
                url,
                headers=headers,
                content=content,
                follow_redirects=False,
                timeout=DEFAULT_TIMEOUT,
            )
        except httpx.TimeoutException:
            failed_timeout = True
        except httpx.RequestError:
            failed_request = True
        if failed_timeout:
            raise PurviewTimeoutError(
                "scanning.timeout",
                f"{operation} timed out",
            )
        if failed_request:
            raise PurviewRequestError(
                "scanning.request_failed",
                f"{operation} transport request failed",
            )
        raise AssertionError("unreachable")

    def list_data_sources(self) -> DataSourceListResult:
        """List Data Sources, following same-origin absolute ``nextLink`` values."""
        url = self._data_sources_url()
        aggregated: list[dict[str, Any]] = []
        seen_links: set[str] = set()
        pages = 0

        while True:
            pages += 1
            if pages > MAX_LIST_PAGES:
                raise PurviewPaginationError(
                    "scanning.pagination_limit_exceeded",
                    "list pagination exceeded the maximum number of pages",
                )

            headers = {
                "Authorization": self._authorization_header(),
                "Accept": "application/json",
            }
            response = self._send("GET", url, operation="list_data_sources", headers=headers)
            if response.status_code != 200:
                self._raise_http_error(
                    response,
                    operation="list_data_sources",
                    method="GET",
                    url=url,
                )

            data = _parse_json_object(response, operation="list_data_sources")
            items, next_link = _validate_list_page(data)
            aggregated.extend(items)

            if next_link is None:
                break
            if next_link in seen_links:
                raise PurviewPaginationError(
                    "scanning.pagination_loop",
                    "list pagination encountered a repeated nextLink",
                )
            seen_links.add(next_link)
            # Validate before any follow request (no Authorization on reject).
            url = validate_absolute_same_origin_next_link(next_link, self._origin)

        return DataSourceListResult(items=tuple(aggregated))

    def get_data_source(self, name: str) -> dict[str, Any]:
        """Get a single Data Source by name (defensive snapshot)."""
        validated = validate_data_source_name(name)
        url = self._data_sources_url(validated)
        headers = {
            "Authorization": self._authorization_header(),
            "Accept": "application/json",
        }
        response = self._send("GET", url, operation="get_data_source", headers=headers)
        if response.status_code != 200:
            self._raise_http_error(
                response,
                operation="get_data_source",
                method="GET",
                url=url,
            )
        data = _parse_json_object(response, operation="get_data_source")
        return _defensive_snapshot(data)

    def _create_or_replace_data_source(
        self,
        name: str,
        payload: Mapping[str, Any],
    ) -> DataSourceWriteReceipt:
        """Internal create-or-replace primitive (not automatic apply).

        Returns a sanitized write receipt when HTTP 200/201 is received. Response
        body is intentionally not required for confirmed-write accounting and is
        never returned to callers.
        """
        validated = validate_data_source_name(name)
        body = _serialize_json_body(payload)
        url = self._data_sources_url(validated)
        headers = {
            "Authorization": self._authorization_header(),
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        response = self._send(
            "PUT",
            url,
            operation="create_or_replace_data_source",
            headers=headers,
            content=body,
        )
        if response.status_code not in {200, 201}:
            self._raise_http_error(
                response,
                operation="create_or_replace_data_source",
                method="PUT",
                url=url,
            )
        # Confirmed write at HTTP success; do not depend on body parse for accounting.
        return DataSourceWriteReceipt(name=validated, status_code=response.status_code)
