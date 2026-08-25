"""Deterministic local Unified Catalog contract-test server."""

from __future__ import annotations

import copy
import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from purview_governance.unified_catalog.constants import (
    BUSINESS_DOMAINS_PATH,
    DATA_ASSETS_PATH,
    DATA_COLUMNS_QUERY_PATH,
    DATA_PRODUCTS_PATH,
    GLOSSARY_TERMS_PATH,
    UNIFIED_CATALOG_API_VERSION,
)
from tests.contract.auth import authorization_is_valid

SECRET_SENTINEL_CONTRACT_401 = "SECRET_SENTINEL_contract_401"
SECRET_SENTINEL_CONTRACT_403 = "SECRET_SENTINEL_contract_403"
SECRET_SENTINEL_CONTRACT_404 = "SECRET_SENTINEL_contract_404"
SECRET_SENTINEL_CONTRACT_429 = "SECRET_SENTINEL_contract_429"
SECRET_SENTINEL_CONTRACT_500 = "SECRET_SENTINEL_contract_500"


def fictional_business_domain_item(
    *,
    domain_id: str = "7e74f902-62f5-49f4-8258-92ed2b8537ba",
    name: str = "fictional-sales-domain",
) -> dict[str, Any]:
    """Build a fictional Business Domain item for contract/unit fixtures."""
    return {
        "id": domain_id,
        "name": name,
        "status": "PUBLISHED",
        "type": "FunctionalUnit",
        "systemData": {
            "createdAt": "1970-01-01T00:00:00.000Z",
            "createdBy": "00000000-0000-0000-0000-000000000001",
            "lastModifiedAt": "1970-01-01T00:00:00.000Z",
            "lastModifiedBy": "00000000-0000-0000-0000-000000000001",
        },
    }


def paged_domains_fixture(
    items: list[dict[str, Any]],
    *,
    next_link: str | None = None,
) -> dict[str, Any]:
    """Build a PagedDomain response body."""
    body: dict[str, Any] = {"value": list(items)}
    if next_link is not None:
        body["nextLink"] = next_link
    return body


@dataclass(frozen=True, slots=True)
class RecordedRequest:
    method: str
    path: str
    api_version: str | None
    accept: str | None
    authorization_present: bool
    authorization_valid: bool
    skip_token: str | None = None
    write_only: str | None = None
    json_body: dict[str, Any] | None = None


def paged_data_products_fixture(
    items: list[dict[str, Any]],
    *,
    next_link: str | None = None,
) -> dict[str, Any]:
    """Build a PagedDataProduct response body."""
    body: dict[str, Any] = {"value": list(items)}
    if next_link is not None:
        body["nextLink"] = next_link
    return body


def fictional_data_product_item(
    *,
    product_id: str = "40000000-0000-4000-8000-000000000001",
    name: str = "fictional-sales-product",
    domain_id: str = "10000000-0000-4000-8000-000000000001",
    product_type: str = "Master",
    owner_id: str = "30000000-0000-4000-8000-000000000001",
) -> dict[str, Any]:
    """Build a fictional Data Product item for contract/unit fixtures."""
    return {
        "id": product_id,
        "name": name,
        "domain": domain_id,
        "type": product_type,
        "description": "Fictional data product description",
        "businessUse": "Fictional business use",
        "status": "DRAFT",
        "contacts": {
            "owner": [{"id": owner_id}],
        },
        "systemData": {
            "createdAt": "1970-01-01T00:00:00.000Z",
            "createdBy": "00000000-0000-0000-0000-000000000001",
            "lastModifiedAt": "1970-01-01T00:00:00.000Z",
            "lastModifiedBy": "00000000-0000-0000-0000-000000000001",
        },
    }


def paged_glossary_terms_fixture(
    items: list[dict[str, Any]],
    *,
    next_link: str | None = None,
) -> dict[str, Any]:
    """Build a PagedTerm response body."""
    body: dict[str, Any] = {"value": list(items)}
    if next_link is not None:
        body["nextLink"] = next_link
    return body


def fictional_glossary_term_item(
    *,
    term_id: str = "50000000-0000-4000-8000-000000000001",
    name: str = "fictional-glossary-term",
    domain_id: str = "10000000-0000-4000-8000-000000000001",
    parent_id: str | None = None,
    acronyms: list[str] | None = None,
    owner_id: str = "30000000-0000-4000-8000-000000000001",
    status: str = "DRAFT",
) -> dict[str, Any]:
    """Build a fictional Glossary Term item for contract/unit fixtures."""
    item: dict[str, Any] = {
        "id": term_id,
        "name": name,
        "domain": domain_id,
        "description": "Fictional glossary term description",
        "status": status,
        "contacts": {
            "owner": [{"id": owner_id}],
        },
        "systemData": {
            "createdAt": "1970-01-01T00:00:00.000Z",
            "createdBy": "00000000-0000-0000-0000-000000000001",
            "lastModifiedAt": "1970-01-01T00:00:00.000Z",
            "lastModifiedBy": "00000000-0000-0000-0000-000000000001",
        },
    }
    if parent_id is not None:
        item["parentId"] = parent_id
    if acronyms is not None:
        item["acronyms"] = acronyms
    return item


def paged_data_assets_fixture(
    items: list[dict[str, Any]],
    *,
    next_link: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"value": list(items)}
    if next_link is not None:
        body["nextLink"] = next_link
    return body


def fictional_data_asset_item(
    *,
    asset_id: str = "60000000-0000-4000-8000-000000000001",
    name: str = "fictional-data-asset",
    asset_type: str = "General",
) -> dict[str, Any]:
    return {
        "id": asset_id,
        "name": name,
        "type": asset_type,
        "source": {
            "type": "AzureSqlTable",
            "assetId": "70000000-0000-4000-8000-000000000001",
            "assetType": "AzureSqlTable",
            "fqn": "sqlserver.database.schema.table",
            "accountName": "fictional-account",
            "assetAttributes": ["attr1"],
        },
        "systemData": {
            "createdAt": "1970-01-01T00:00:00.000Z",
            "createdBy": "00000000-0000-0000-0000-000000000001",
            "lastModifiedAt": "1970-01-01T00:00:00.000Z",
            "lastModifiedBy": "00000000-0000-0000-0000-000000000001",
            "provisioningState": "Succeeded",
        },
    }


def paged_data_columns_fixture(
    items: list[dict[str, Any]],
    *,
    next_link: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"value": list(items)}
    if next_link is not None:
        body["nextLink"] = next_link
    return body


def fictional_data_column_item(
    *,
    column_id: str = "80000000-0000-4000-8000-000000000001",
    name: str = "fictional-column",
    column_type: str = "General",
) -> dict[str, Any]:
    return {
        "id": column_id,
        "name": name,
        "type": column_type,
        "source": {
            "type": "AzureSqlColumn",
            "assetId": "70000000-0000-4000-8000-000000000001",
            "columnId": "90000000-0000-4000-8000-000000000001",
            "assetType": "AzureSqlTable",
            "fqn": "sqlserver.database.schema.table.column",
            "accountName": "fictional-account",
            "assetAttributes": ["attr1"],
        },
        "columnDetails": {"dataType": "varchar", "isNullable": True},
        "assetDetails": {"assetId": "dg-asset-string-id", "name": "parent-asset"},
    }


def paged_relationships_fixture(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {"value": list(items)}


@dataclass
class UnifiedCatalogScenarioState:
    enumerate_mode: str = "success"
    enumerate_items: list[dict[str, Any]] = field(default_factory=list)
    enumerate_page2_items: list[dict[str, Any]] = field(default_factory=list)
    enumerate_next_link: str | None = None
    cross_origin_next_link: str | None = None
    enumerate_data_products_mode: str = "success"
    enumerate_data_products_items: list[dict[str, Any]] = field(default_factory=list)
    enumerate_data_products_page2_items: list[dict[str, Any]] = field(default_factory=list)
    enumerate_data_products_next_link: str | None = None
    enumerate_glossary_terms_mode: str = "success"
    enumerate_glossary_terms_items: list[dict[str, Any]] = field(default_factory=list)
    enumerate_glossary_terms_page2_items: list[dict[str, Any]] = field(default_factory=list)
    enumerate_glossary_terms_next_link: str | None = None
    enumerate_data_assets_mode: str = "success"
    enumerate_data_assets_items: list[dict[str, Any]] = field(default_factory=list)
    enumerate_data_assets_page2_items: list[dict[str, Any]] = field(default_factory=list)
    enumerate_data_assets_next_link: str | None = None
    query_data_columns_mode: str = "success"
    query_data_columns_items: list[dict[str, Any]] = field(default_factory=list)
    query_data_columns_page2_items: list[dict[str, Any]] = field(default_factory=list)
    query_data_columns_next_link: str | None = None
    data_product_relationships: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    glossary_term_relationships: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    column_query_requests: list[dict[str, Any]] = field(default_factory=list)
    recordings: list[RecordedRequest] = field(default_factory=list)
    business_domains_by_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    data_products_by_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    glossary_terms_by_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    write_mode: str = "success"
    targeted_get_counts: dict[tuple[str, str], int] = field(default_factory=dict)
    second_preflight_fail_after_writes: int | None = None
    second_preflight_fail_kind: str | None = None
    apply_writes_completed: int = 0


@dataclass(frozen=True, slots=True)
class UnifiedCatalogContractServer:
    host: str
    port: int
    state: UnifiedCatalogScenarioState

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _make_handler(state: UnifiedCatalogScenarioState) -> type[BaseHTTPRequestHandler]:
    class UnifiedCatalogContractHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

        def _record(self, *, json_body: dict[str, Any] | None = None) -> None:
            auth = self.headers.get("Authorization")
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            api_versions = query.get("api-version", [])
            skip_tokens = query.get("$skipToken", [])
            write_only = query.get("writeOnly", [])
            state.recordings.append(
                RecordedRequest(
                    method=self.command,
                    path=parsed.path,
                    api_version=api_versions[0] if api_versions else None,
                    accept=self.headers.get("Accept"),
                    authorization_present=auth is not None,
                    authorization_valid=authorization_is_valid(auth),
                    skip_token=skip_tokens[0] if skip_tokens else None,
                    write_only=write_only[0] if write_only else None,
                    json_body=copy.deepcopy(json_body) if json_body is not None else None,
                )
            )

        def _read_json_body(self) -> dict[str, Any] | None:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                return None
            raw = self.rfile.read(length)
            try:
                body = json.loads(raw.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return None
            if not isinstance(body, dict):
                return None
            return body

        def _resource_id_from_collection_path(
            self,
            parsed: Any,
            collection_path: str,
        ) -> str | None:
            prefix = f"{collection_path}/"
            if not parsed.path.startswith(prefix):
                return None
            remainder = parsed.path[len(prefix) :]
            if not remainder or "/" in remainder:
                return None
            return remainder

        def _business_domain_items(self) -> list[dict[str, Any]]:
            if state.business_domains_by_id:
                return list(state.business_domains_by_id.values())
            return state.enumerate_items or [fictional_business_domain_item()]

        def _data_product_items(self) -> list[dict[str, Any]]:
            if state.data_products_by_id:
                return list(state.data_products_by_id.values())
            return list(state.enumerate_data_products_items)

        def _glossary_term_items(self) -> list[dict[str, Any]]:
            if state.glossary_terms_by_id:
                return list(state.glossary_terms_by_id.values())
            return list(state.enumerate_glossary_terms_items)

        def _track_targeted_get(self, resource_kind: str, resource_id: str) -> int:
            key = (resource_kind, resource_id)
            count = state.targeted_get_counts.get(key, 0) + 1
            state.targeted_get_counts[key] = count
            return count

        def _second_preflight_should_fail(self) -> bool:
            threshold = state.second_preflight_fail_after_writes
            if threshold is None:
                return False
            return state.apply_writes_completed >= threshold

        def _handle_get_business_domain_by_id(self, parsed: Any, domain_id: str) -> None:
            if not self._validate_api_version(parsed):
                return
            get_count = self._track_targeted_get("businessDomain", domain_id)
            if (
                self._second_preflight_should_fail()
                and state.second_preflight_fail_kind == "auth"
                and get_count == 2
            ):
                self._send_json(401, {"error": {"code": "Unauthorized"}})
                return
            if (
                self._second_preflight_should_fail()
                and state.second_preflight_fail_kind == "read"
                and get_count == 2
            ):
                self._send_json(500, {"error": {"code": "ServerError"}})
                return
            item = state.business_domains_by_id.get(domain_id)
            if item is None:
                self._send_json(404, {"error": {"code": "NotFound"}})
                return
            payload = copy.deepcopy(item)
            if (
                self._second_preflight_should_fail()
                and state.second_preflight_fail_kind == "stale"
                and get_count == 2
            ):
                payload["name"] = f"{payload.get('name', 'domain')}-stale-drift"
            self._send_json(200, payload)

        def _handle_get_data_product_by_id(self, parsed: Any, product_id: str) -> None:
            if not self._validate_api_version(parsed):
                return
            get_count = self._track_targeted_get("dataProduct", product_id)
            if (
                self._second_preflight_should_fail()
                and state.second_preflight_fail_kind == "auth"
                and get_count == 2
            ):
                self._send_json(401, {"error": {"code": "Unauthorized"}})
                return
            if (
                self._second_preflight_should_fail()
                and state.second_preflight_fail_kind == "read"
                and get_count == 2
            ):
                self._send_json(500, {"error": {"code": "ServerError"}})
                return
            item = state.data_products_by_id.get(product_id)
            if item is None:
                self._send_json(404, {"error": {"code": "NotFound"}})
                return
            payload = copy.deepcopy(item)
            if (
                self._second_preflight_should_fail()
                and state.second_preflight_fail_kind == "stale"
                and get_count == 2
            ):
                payload["name"] = f"{payload.get('name', 'product')}-stale-drift"
            self._send_json(200, payload)

        def _handle_get_glossary_term_by_id(self, parsed: Any, term_id: str) -> None:
            if not self._validate_api_version(parsed):
                return
            get_count = self._track_targeted_get("glossaryTerm", term_id)
            if (
                self._second_preflight_should_fail()
                and state.second_preflight_fail_kind == "auth"
                and get_count == 2
            ):
                self._send_json(401, {"error": {"code": "Unauthorized"}})
                return
            if (
                self._second_preflight_should_fail()
                and state.second_preflight_fail_kind == "read"
                and get_count == 2
            ):
                self._send_json(500, {"error": {"code": "ServerError"}})
                return
            item = state.glossary_terms_by_id.get(term_id)
            if item is None:
                self._send_json(404, {"error": {"code": "NotFound"}})
                return
            payload = copy.deepcopy(item)
            if (
                self._second_preflight_should_fail()
                and state.second_preflight_fail_kind == "stale"
                and get_count == 2
            ):
                payload["name"] = f"{payload.get('name', 'term')}-stale-drift"
            self._send_json(200, payload)

        def _handle_write_failure(self) -> bool:
            mode = state.write_mode
            if mode == "success":
                return False
            if mode == "unauthorized":
                self._send_json(401, {"error": {"code": "Unauthorized"}})
                return True
            if mode == "forbidden":
                self._send_json(403, {"error": {"code": "Forbidden"}})
                return True
            if mode == "client_error":
                self._send_json(400, {"error": {"code": "BadRequest"}})
                return True
            if mode == "server_error":
                self._send_json(500, {"error": {"code": "ServerError"}})
                return True
            return False

        def _handle_put_business_domain(
            self,
            parsed: Any,
            domain_id: str,
            body: dict[str, Any],
        ) -> None:
            if not self._validate_api_version(parsed):
                return
            if self._handle_write_failure():
                return
            merged = copy.deepcopy(body)
            merged["id"] = domain_id
            state.business_domains_by_id[domain_id] = merged
            state.apply_writes_completed += 1
            self._send_json(200, merged)

        def _handle_put_data_product(
            self,
            parsed: Any,
            product_id: str,
            body: dict[str, Any],
        ) -> None:
            if not self._validate_api_version(parsed):
                return
            if self._handle_write_failure():
                return
            merged = copy.deepcopy(body)
            merged["id"] = product_id
            state.data_products_by_id[product_id] = merged
            state.apply_writes_completed += 1
            self._send_json(200, merged)

        def _handle_put_glossary_term(
            self,
            parsed: Any,
            term_id: str,
            body: dict[str, Any],
        ) -> None:
            if not self._validate_api_version(parsed):
                return
            if self._handle_write_failure():
                return
            merged = copy.deepcopy(body)
            merged["id"] = term_id
            state.glossary_terms_by_id[term_id] = merged
            state.apply_writes_completed += 1
            self._send_json(200, merged)

        def _handle_post_data_product(self, parsed: Any, body: dict[str, Any]) -> None:
            if not self._validate_api_version(parsed):
                return
            if self._handle_write_failure():
                return
            product_id = body.get("id")
            if not isinstance(product_id, str):
                self._send_json(400, {"error": {"code": "InvalidRequest"}})
                return
            created = copy.deepcopy(body)
            state.data_products_by_id[product_id] = created
            state.apply_writes_completed += 1
            self._send_json(201, created)

        def _handle_post_glossary_term(self, parsed: Any, body: dict[str, Any]) -> None:
            if not self._validate_api_version(parsed):
                return
            if self._handle_write_failure():
                return
            term_id = body.get("id")
            if not isinstance(term_id, str):
                self._send_json(400, {"error": {"code": "InvalidRequest"}})
                return
            created = copy.deepcopy(body)
            state.glossary_terms_by_id[term_id] = created
            state.apply_writes_completed += 1
            self._send_json(201, created)

        def _handle_post_business_domain_rejected(self, parsed: Any) -> None:
            if not self._validate_api_version(parsed):
                return
            self._send_json(
                405,
                {
                    "error": {
                        "code": "MethodNotAllowed",
                        "message": "POST /businessdomains is not supported",
                    },
                },
            )

        def _send_json(self, status: int, payload: Any) -> None:
            body = _json_bytes(payload)
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("x-ms-request-id", "unified-catalog-contract-fixture")
            self.end_headers()
            self.wfile.write(body)

        def _send_raw(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _require_auth(self) -> bool:
            return authorization_is_valid(self.headers.get("Authorization"))

        def _validate_api_version(self, parsed: Any) -> bool:
            query = parse_qs(parsed.query)
            versions = query.get("api-version", [])
            if not versions or versions[0] != UNIFIED_CATALOG_API_VERSION:
                self._send_json(
                    400,
                    {"error": {"code": "InvalidApiVersion", "message": "api-version mismatch"}},
                )
                return False
            return True

        def _handle_enumerate_data_products(self, parsed: Any) -> None:
            if not self._validate_api_version(parsed):
                return

            mode = state.enumerate_data_products_mode
            if mode == "unauthorized":
                self._send_json(401, {"error": {"code": "Unauthorized"}})
                return
            if mode == "forbidden":
                self._send_json(
                    403, {"error": {"code": "Forbidden", "message": SECRET_SENTINEL_CONTRACT_403}}
                )
                return
            if mode == "not_found":
                self._send_json(
                    404, {"error": {"code": "NotFound", "message": SECRET_SENTINEL_CONTRACT_404}}
                )
                return
            if mode == "throttled":
                self._send_json(
                    429,
                    {"error": {"code": "TooManyRequests", "message": SECRET_SENTINEL_CONTRACT_429}},
                )
                return
            if mode == "server_error":
                self._send_json(
                    500, {"error": {"code": "ServerError", "message": SECRET_SENTINEL_CONTRACT_500}}
                )
                return
            if mode == "bad_json":
                self._send_raw(200, b"not-json", "application/json")
                return
            if mode == "bad_shape":
                self._send_json(200, {"value": "not-an-array"})
                return
            if mode == "paginated":
                query = parse_qs(parsed.query)
                if "$skipToken" in query:
                    items = state.enumerate_data_products_page2_items or [
                        fictional_data_product_item(
                            product_id="bbbbbbbb-bbbb-cccc-dddd-eeeeeeeeeeee",
                            name="fictional-product-page-two",
                        )
                    ]
                    self._send_json(200, paged_data_products_fixture(items))
                    return
                page_one = self._data_product_items() or [fictional_data_product_item()]
                token = "fictional-data-product-skip-token"
                next_link = state.enumerate_data_products_next_link or (
                    f"http://127.0.0.1:{self.server.server_address[1]}"
                    f"{DATA_PRODUCTS_PATH}"
                    f"?api-version={UNIFIED_CATALOG_API_VERSION}&$skipToken={token}"
                )
                self._send_json(200, paged_data_products_fixture(page_one, next_link=next_link))
                return

            items = self._data_product_items()
            self._send_json(200, paged_data_products_fixture(items))

        def _handle_enumerate_glossary_terms(self, parsed: Any) -> None:
            if not self._validate_api_version(parsed):
                return

            mode = state.enumerate_glossary_terms_mode
            if mode == "unauthorized":
                self._send_json(401, {"error": {"code": "Unauthorized"}})
                return
            if mode == "forbidden":
                self._send_json(
                    403, {"error": {"code": "Forbidden", "message": SECRET_SENTINEL_CONTRACT_403}}
                )
                return
            if mode == "not_found":
                self._send_json(
                    404, {"error": {"code": "NotFound", "message": SECRET_SENTINEL_CONTRACT_404}}
                )
                return
            if mode == "throttled":
                self._send_json(
                    429,
                    {"error": {"code": "TooManyRequests", "message": SECRET_SENTINEL_CONTRACT_429}},
                )
                return
            if mode == "server_error":
                self._send_json(
                    500, {"error": {"code": "ServerError", "message": SECRET_SENTINEL_CONTRACT_500}}
                )
                return
            if mode == "bad_json":
                self._send_raw(200, b"not-json", "application/json")
                return
            if mode == "bad_shape":
                self._send_json(200, {"value": "not-an-array"})
                return
            if mode == "paginated":
                query = parse_qs(parsed.query)
                if "$skipToken" in query:
                    items = state.enumerate_glossary_terms_page2_items or [
                        fictional_glossary_term_item(
                            term_id="cccccccc-bbbb-cccc-dddd-eeeeeeeeeeee",
                            name="fictional-term-page-two",
                        )
                    ]
                    self._send_json(200, paged_glossary_terms_fixture(items))
                    return
                page_one = self._glossary_term_items() or [fictional_glossary_term_item()]
                token = "fictional-glossary-term-skip-token"
                next_link = state.enumerate_glossary_terms_next_link or (
                    f"http://127.0.0.1:{self.server.server_address[1]}"
                    f"{GLOSSARY_TERMS_PATH}"
                    f"?api-version={UNIFIED_CATALOG_API_VERSION}&$skipToken={token}"
                )
                self._send_json(200, paged_glossary_terms_fixture(page_one, next_link=next_link))
                return

            items = self._glossary_term_items()
            self._send_json(200, paged_glossary_terms_fixture(items))

        def _handle_enumerate_data_assets(self, parsed: Any) -> None:
            if not self._validate_api_version(parsed):
                return
            mode = state.enumerate_data_assets_mode
            if mode == "bad_shape":
                self._send_json(200, {"value": "not-an-array"})
                return
            if mode == "paginated":
                query = parse_qs(parsed.query)
                if "$skipToken" in query:
                    items = state.enumerate_data_assets_page2_items or [
                        fictional_data_asset_item(
                            asset_id="dddddddd-bbbb-cccc-dddd-eeeeeeeeeeee",
                            name="fictional-asset-page-two",
                        )
                    ]
                    self._send_json(200, paged_data_assets_fixture(items))
                    return
                page_one = state.enumerate_data_assets_items or [fictional_data_asset_item()]
                token = "fictional-data-asset-skip-token"
                next_link = state.enumerate_data_assets_next_link or (
                    f"http://127.0.0.1:{self.server.server_address[1]}"
                    f"{DATA_ASSETS_PATH}"
                    f"?api-version={UNIFIED_CATALOG_API_VERSION}&$skipToken={token}"
                )
                self._send_json(200, paged_data_assets_fixture(page_one, next_link=next_link))
                return
            items = state.enumerate_data_assets_items or [fictional_data_asset_item()]
            self._send_json(200, paged_data_assets_fixture(items))

        def _handle_query_data_columns(self, parsed: Any, body: dict[str, Any]) -> None:
            if not self._validate_api_version(parsed):
                return
            state.column_query_requests.append(dict(body))
            mode = state.query_data_columns_mode
            if mode == "bad_shape":
                self._send_json(200, {"value": "not-an-array"})
                return
            if mode == "empty_next_link":
                next_link = (
                    f"http://127.0.0.1:{self.server.server_address[1]}"
                    f"{DATA_COLUMNS_QUERY_PATH}"
                    f"?api-version={UNIFIED_CATALOG_API_VERSION}"
                )
                self._send_json(200, paged_data_columns_fixture([], next_link=next_link))
                return
            if mode == "foreign_next_link":
                item = fictional_data_column_item()
                foreign = state.cross_origin_next_link or "https://evil.example/continue"
                self._send_json(200, paged_data_columns_fixture([item], next_link=foreign))
                return
            if mode == "malformed_next_link":
                self._send_json(
                    200,
                    {"value": [fictional_data_column_item()], "nextLink": 123},
                )
                return
            if mode == "full_page":
                skip = int(body.get("skip", 0))
                if skip > 0:
                    self._send_json(200, paged_data_columns_fixture([]))
                    return
                page = state.query_data_columns_items or [fictional_data_column_item()]
                self._send_json(200, paged_data_columns_fixture(page))
                return
            skip = int(body.get("skip", 0))
            if skip > 0:
                items = state.query_data_columns_page2_items or [
                    fictional_data_column_item(
                        column_id="eeeeeeee-bbbb-cccc-dddd-eeeeeeeeeeee",
                        name="fictional-column-page-two",
                    )
                ]
                self._send_json(200, paged_data_columns_fixture(items))
                return
            page_one = state.query_data_columns_items or [fictional_data_column_item()]
            if state.query_data_columns_page2_items or state.query_data_columns_next_link:
                next_link = state.query_data_columns_next_link or (
                    f"http://127.0.0.1:{self.server.server_address[1]}"
                    f"{DATA_COLUMNS_QUERY_PATH}"
                    f"?api-version={UNIFIED_CATALOG_API_VERSION}"
                )
                self._send_json(200, paged_data_columns_fixture(page_one, next_link=next_link))
                return
            self._send_json(200, paged_data_columns_fixture(page_one))

        def _handle_relationships(self, parsed: Any) -> None:
            if not self._validate_api_version(parsed):
                return
            parts = parsed.path.split("/")
            if len(parts) < 5 or parts[-1] != "relationships":
                self._send_json(404, {"error": {"code": "NotFound"}})
                return
            resource_kind = parts[-3]
            resource_id = parts[-2]
            query = parse_qs(parsed.query)
            if resource_kind == "dataProducts":
                items = state.data_product_relationships.get(resource_id, [])
            elif resource_kind == "terms":
                entity_type = query.get("entityType", [""])[0]
                key = f"{resource_id}:{entity_type}"
                items = state.glossary_term_relationships.get(key, [])
            else:
                self._send_json(404, {"error": {"code": "NotFound"}})
                return
            self._send_json(200, paged_relationships_fixture(items))

        def _handle_enumerate(self, parsed: Any) -> None:
            if not self._validate_api_version(parsed):
                return

            mode = state.enumerate_mode
            if mode == "unauthorized":
                self._send_json(401, {"error": {"code": "Unauthorized"}})
                return
            if mode == "forbidden":
                self._send_json(
                    403, {"error": {"code": "Forbidden", "message": SECRET_SENTINEL_CONTRACT_403}}
                )
                return
            if mode == "not_found":
                self._send_json(
                    404, {"error": {"code": "NotFound", "message": SECRET_SENTINEL_CONTRACT_404}}
                )
                return
            if mode == "throttled":
                self._send_json(
                    429,
                    {"error": {"code": "TooManyRequests", "message": SECRET_SENTINEL_CONTRACT_429}},
                )
                return
            if mode == "server_error":
                self._send_json(
                    500, {"error": {"code": "ServerError", "message": SECRET_SENTINEL_CONTRACT_500}}
                )
                return
            if mode == "bad_json":
                self._send_raw(200, b"not-json", "application/json")
                return
            if mode == "bad_shape":
                self._send_json(200, {"value": "not-an-array"})
                return
            if mode == "cross_origin_next_link":
                item = fictional_business_domain_item(name="page-one")
                link = state.cross_origin_next_link or "https://evil.example/continue"
                self._send_json(200, paged_domains_fixture([item], next_link=link))
                return
            if mode == "paginated":
                query = parse_qs(parsed.query)
                if "$skipToken" in query:
                    items = state.enumerate_page2_items or [
                        fictional_business_domain_item(
                            domain_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                            name="fictional-page-two",
                        )
                    ]
                    self._send_json(200, paged_domains_fixture(items))
                    return
                page_one = state.enumerate_items or [fictional_business_domain_item()]
                token = "fictional-skip-token-abc"
                next_link = state.enumerate_next_link or (
                    f"http://127.0.0.1:{self.server.server_address[1]}"
                    f"{BUSINESS_DOMAINS_PATH}"
                    f"?api-version={UNIFIED_CATALOG_API_VERSION}&$skipToken={token}"
                )
                self._send_json(200, paged_domains_fixture(page_one, next_link=next_link))
                return

            items = self._business_domain_items()
            self._send_json(200, paged_domains_fixture(items))

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            self._record()
            if not self._require_auth():
                self._send_json(
                    401,
                    {
                        "error": {
                            "code": "Unauthorized",
                            "message": SECRET_SENTINEL_CONTRACT_401,
                        }
                    },
                )
                return
            domain_id = self._resource_id_from_collection_path(parsed, BUSINESS_DOMAINS_PATH)
            if domain_id is not None:
                self._handle_get_business_domain_by_id(parsed, domain_id)
                return
            product_id = self._resource_id_from_collection_path(parsed, DATA_PRODUCTS_PATH)
            if product_id is not None and not parsed.path.endswith("/relationships"):
                self._handle_get_data_product_by_id(parsed, product_id)
                return
            term_id = self._resource_id_from_collection_path(parsed, GLOSSARY_TERMS_PATH)
            if term_id is not None and not parsed.path.endswith("/relationships"):
                self._handle_get_glossary_term_by_id(parsed, term_id)
                return
            if parsed.path == BUSINESS_DOMAINS_PATH:
                self._handle_enumerate(parsed)
                return
            if parsed.path == DATA_PRODUCTS_PATH:
                self._handle_enumerate_data_products(parsed)
                return
            if parsed.path == GLOSSARY_TERMS_PATH:
                self._handle_enumerate_glossary_terms(parsed)
                return
            if parsed.path == DATA_ASSETS_PATH:
                self._handle_enumerate_data_assets(parsed)
                return
            if parsed.path.endswith("/relationships"):
                self._handle_relationships(parsed)
                return
            self._send_json(404, {"error": {"code": "NotFound"}})

        def do_PUT(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            body = self._read_json_body()
            self._record(json_body=body)
            if not self._require_auth():
                self._send_json(401, {"error": {"code": "Unauthorized"}})
                return
            if body is None:
                self._send_json(400, {"error": {"code": "InvalidRequest"}})
                return
            domain_id = self._resource_id_from_collection_path(parsed, BUSINESS_DOMAINS_PATH)
            if domain_id is not None:
                self._handle_put_business_domain(parsed, domain_id, body)
                return
            product_id = self._resource_id_from_collection_path(parsed, DATA_PRODUCTS_PATH)
            if product_id is not None:
                self._handle_put_data_product(parsed, product_id, body)
                return
            term_id = self._resource_id_from_collection_path(parsed, GLOSSARY_TERMS_PATH)
            if term_id is not None:
                self._handle_put_glossary_term(parsed, term_id, body)
                return
            self._send_json(404, {"error": {"code": "NotFound"}})

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            body = self._read_json_body()
            self._record(json_body=body)
            if parsed.path == BUSINESS_DOMAINS_PATH:
                if not self._require_auth():
                    self._send_json(401, {"error": {"code": "Unauthorized"}})
                    return
                self._handle_post_business_domain_rejected(parsed)
                return
            if parsed.path == DATA_PRODUCTS_PATH:
                if not self._require_auth():
                    self._send_json(401, {"error": {"code": "Unauthorized"}})
                    return
                if body is None:
                    self._send_json(400, {"error": {"code": "InvalidRequest"}})
                    return
                self._handle_post_data_product(parsed, body)
                return
            if parsed.path == GLOSSARY_TERMS_PATH:
                if not self._require_auth():
                    self._send_json(401, {"error": {"code": "Unauthorized"}})
                    return
                if body is None:
                    self._send_json(400, {"error": {"code": "InvalidRequest"}})
                    return
                self._handle_post_glossary_term(parsed, body)
                return
            if parsed.path != DATA_COLUMNS_QUERY_PATH:
                self._send_json(404, {"error": {"code": "NotFound"}})
                return
            if not self._require_auth():
                self._send_json(401, {"error": {"code": "Unauthorized"}})
                return
            if body is None:
                self._send_json(400, {"error": {"code": "InvalidRequest"}})
                return
            self._handle_query_data_columns(parsed, body)

    return UnifiedCatalogContractHandler


@contextmanager
def start_unified_catalog_contract_server(
    *,
    enumerate_mode: str = "success",
    enumerate_items: list[dict[str, Any]] | None = None,
    enumerate_page2_items: list[dict[str, Any]] | None = None,
    enumerate_next_link: str | None = None,
    cross_origin_next_link: str | None = None,
    enumerate_data_products_mode: str = "success",
    enumerate_data_products_items: list[dict[str, Any]] | None = None,
    enumerate_data_products_page2_items: list[dict[str, Any]] | None = None,
    enumerate_data_products_next_link: str | None = None,
    enumerate_glossary_terms_mode: str = "success",
    enumerate_glossary_terms_items: list[dict[str, Any]] | None = None,
    enumerate_glossary_terms_page2_items: list[dict[str, Any]] | None = None,
    enumerate_glossary_terms_next_link: str | None = None,
    enumerate_data_assets_mode: str = "success",
    enumerate_data_assets_items: list[dict[str, Any]] | None = None,
    enumerate_data_assets_page2_items: list[dict[str, Any]] | None = None,
    enumerate_data_assets_next_link: str | None = None,
    query_data_columns_mode: str = "success",
    query_data_columns_items: list[dict[str, Any]] | None = None,
    query_data_columns_page2_items: list[dict[str, Any]] | None = None,
    query_data_columns_next_link: str | None = None,
    data_product_relationships: dict[str, list[dict[str, Any]]] | None = None,
    glossary_term_relationships: dict[str, list[dict[str, Any]]] | None = None,
    write_mode: str = "success",
    second_preflight_fail_after_writes: int | None = None,
    second_preflight_fail_kind: str | None = None,
) -> Iterator[UnifiedCatalogContractServer]:
    """Start a daemon Unified Catalog contract server on an ephemeral loopback port."""
    state = UnifiedCatalogScenarioState(
        enumerate_mode=enumerate_mode,
        enumerate_items=list(enumerate_items or []),
        enumerate_page2_items=list(enumerate_page2_items or []),
        enumerate_next_link=enumerate_next_link,
        cross_origin_next_link=cross_origin_next_link,
        enumerate_data_products_mode=enumerate_data_products_mode,
        enumerate_data_products_items=list(enumerate_data_products_items or []),
        enumerate_data_products_page2_items=list(enumerate_data_products_page2_items or []),
        enumerate_data_products_next_link=enumerate_data_products_next_link,
        enumerate_glossary_terms_mode=enumerate_glossary_terms_mode,
        enumerate_glossary_terms_items=list(enumerate_glossary_terms_items or []),
        enumerate_glossary_terms_page2_items=list(enumerate_glossary_terms_page2_items or []),
        enumerate_glossary_terms_next_link=enumerate_glossary_terms_next_link,
        enumerate_data_assets_mode=enumerate_data_assets_mode,
        enumerate_data_assets_items=list(enumerate_data_assets_items or []),
        enumerate_data_assets_page2_items=list(enumerate_data_assets_page2_items or []),
        enumerate_data_assets_next_link=enumerate_data_assets_next_link,
        query_data_columns_mode=query_data_columns_mode,
        query_data_columns_items=list(query_data_columns_items or []),
        query_data_columns_page2_items=list(query_data_columns_page2_items or []),
        query_data_columns_next_link=query_data_columns_next_link,
        data_product_relationships=dict(data_product_relationships or {}),
        glossary_term_relationships=dict(glossary_term_relationships or {}),
        write_mode=write_mode,
        second_preflight_fail_after_writes=second_preflight_fail_after_writes,
        second_preflight_fail_kind=second_preflight_fail_kind,
    )
    domain_seed = list(enumerate_items or [])
    if not domain_seed and not enumerate_page2_items:
        domain_seed = [fictional_business_domain_item()]
    for item in domain_seed:
        state.business_domains_by_id[item["id"]] = copy.deepcopy(item)
    for item in enumerate_data_products_items or []:
        state.data_products_by_id[item["id"]] = copy.deepcopy(item)
    for item in enumerate_glossary_terms_items or []:
        state.glossary_terms_by_id[item["id"]] = copy.deepcopy(item)
    handler = _make_handler(state)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    host, port = httpd.server_address[0], httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    server = UnifiedCatalogContractServer(host=host, port=port, state=state)
    try:
        yield server
    finally:
        with suppress(Exception):
            httpd.shutdown()
        with suppress(Exception):
            httpd.server_close()
        thread.join(timeout=5)
