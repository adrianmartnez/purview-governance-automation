"""Deterministic local Purview Scanning Data Plane contract-test server.

Emulates only the v1 Data Source list/get/create-or-replace surface needed by
offline contract tests. Not a general Purview emulator.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from purview_governance.scanning.constants import SCANNING_API_VERSION

AUTH_SENTINEL = "Bearer TEST_PURVIEW_AUTH_SENTINEL"
HEALTH_PATH = "/health"
HEALTH_PAYLOAD = {"status": "ok", "lane": "api-contract-tests"}


def azure_storage_fixture(
    name: str,
    *,
    creation_type: str = "Manual",
    moving_state: str | dict[str, str] = "Active",
    endpoint: str = "https://example.blob.core.windows.net/",
    collection_ref: str = "Collection-rZX",
    include_timestamps: bool = False,
    include_scans: list[Any] | None = None,
    omit_scans: bool = True,
    observed: dict[str, Any] | None = None,
    extra_top: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a fictional AzureStorage GET body for contract/unit fixtures."""
    properties: dict[str, Any] = {
        "endpoint": endpoint,
        "collection": {
            "referenceName": collection_ref,
            "type": "CollectionReference",
        },
        "dataSourceCollectionMovingState": moving_state,
    }
    if include_timestamps:
        properties["createdAt"] = "2022-08-05T07:13:08.032795Z"
        properties["lastModifiedAt"] = "2022-08-05T07:13:08.032795Z"
        properties["collection"]["lastModifiedAt"] = "2022-08-05T07:13:08.032795Z"
    if observed:
        properties.update(observed)
    body: dict[str, Any] = {
        "name": name,
        "kind": "AzureStorage",
        "creationType": creation_type,
        "properties": properties,
    }
    if not omit_scans:
        body["scans"] = include_scans if include_scans is not None else []
    if extra_top:
        body.update(extra_top)
    return body


@dataclass(frozen=True)
class RecordedRequest:
    method: str
    path: str
    api_version: str | None
    accept: str | None
    content_type: str | None
    authorization_present: bool
    authorization_valid: bool
    json_body: Any | None


@dataclass
class ScenarioState:
    """Mutable per-server scenario knobs selected by tests."""

    # list_mode: one_page, paginated, empty, relative_next, cross_origin,
    # loop_next, bad_shape, bad_json, http_error, multi_unordered,
    # duplicate_names, remote_state_mix
    list_mode: str = "one_page"
    # get_mode: success, not_found, bad_json, bad_shape, identity_mismatch,
    # missing_name, missing_kind, unsupported_kind, unknown_field, sensitive,
    # legacy_moving_zero, scans_empty, scans_nonempty, auto_managed, moving
    get_mode: str = "success"
    # put_mode: created, ok, bad_json, ok_bad_json, created_bad_json,
    # client_error, server_error, disconnect_after_record, script
    put_mode: str = "created"
    put_expected_body: dict[str, Any] | None = None
    # When put_mode == "script", consume one entry per PUT (created/ok/...).
    put_script: list[str] = field(default_factory=list)
    put_script_index: int = 0
    get_bodies: dict[str, dict[str, Any]] = field(default_factory=dict)
    recordings: list[RecordedRequest] = field(default_factory=list)


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _make_handler(state: ScenarioState) -> type[BaseHTTPRequestHandler]:
    class PurviewContractHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

        def _read_json_body(self) -> Any | None:
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length <= 0:
                return None
            raw = self.rfile.read(length)
            return json.loads(raw.decode("utf-8"))

        def _record(self, *, json_body: Any | None = None) -> None:
            auth = self.headers.get("Authorization")
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            api_versions = query.get("api-version", [])
            state.recordings.append(
                RecordedRequest(
                    method=self.command,
                    path=parsed.path,
                    api_version=api_versions[0] if api_versions else None,
                    accept=self.headers.get("Accept"),
                    content_type=self.headers.get("Content-Type"),
                    authorization_present=auth is not None,
                    authorization_valid=auth == AUTH_SENTINEL,
                    json_body=json_body,
                )
            )

        def _send_json(self, status: int, payload: Any) -> None:
            body = _json_bytes(payload)
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("x-ms-request-id", "contract-fixture-request-id")
            self.end_headers()
            self.wfile.write(body)

        def _send_raw(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _require_auth(self) -> bool:
            return self.headers.get("Authorization") == AUTH_SENTINEL

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == HEALTH_PATH:
                self._record()
                self._send_json(200, HEALTH_PAYLOAD)
                return

            self._record()
            if not self._require_auth():
                self._send_json(401, {"error": {"code": "Unauthorized"}})
                return

            if parsed.path == "/scan/datasources":
                self._handle_list()
                return

            if parsed.path.startswith("/scan/datasources/"):
                name = parsed.path.removeprefix("/scan/datasources/")
                if "/" in name or not name:
                    self._send_json(404, {"error": {"code": "NotFound"}})
                    return
                self._handle_get(name)
                return

            self._send_json(404, {"error": {"code": "NotFound"}})

        def do_PUT(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            try:
                body = self._read_json_body()
            except json.JSONDecodeError:
                self._record(json_body=None)
                self._send_json(400, {"error": {"code": "InvalidJson"}})
                return

            self._record(json_body=body)
            if not self._require_auth():
                self._send_json(401, {"error": {"code": "Unauthorized"}})
                return

            if not parsed.path.startswith("/scan/datasources/"):
                self._send_json(404, {"error": {"code": "NotFound"}})
                return

            name = parsed.path.removeprefix("/scan/datasources/")
            if "/" in name or not name:
                self._send_json(404, {"error": {"code": "NotFound"}})
                return

            if state.put_expected_body is not None and body != state.put_expected_body:
                self._send_json(400, {"error": {"code": "BodyMismatch"}})
                return

            mode = state.put_mode
            if mode == "script":
                if state.put_script_index >= len(state.put_script):
                    self._send_json(500, {"error": {"code": "ScriptExhausted"}})
                    return
                mode = state.put_script[state.put_script_index]
                state.put_script_index += 1

            if mode in {"bad_json", "ok_bad_json"}:
                self._send_raw(200, b"not-json", "application/json")
                return
            if mode == "created_bad_json":
                self._send_raw(201, b"not-json", "application/json")
                return
            if mode == "client_error":
                self._send_json(
                    409,
                    {"error": {"code": "Conflict", "message": "SECRET_SENTINEL_contract_4xx"}},
                )
                return
            if mode == "server_error":
                self._send_json(
                    503,
                    {"error": {"code": "Unavailable", "message": "SECRET_SENTINEL_contract_5xx"}},
                )
                return
            if mode == "disconnect_after_record":
                # Close without a usable HTTP response after recording the PUT.
                with suppress(OSError):
                    self.connection.close()
                return

            response = {"name": name, "kind": (body or {}).get("kind", "AzureStorage")}
            status = 201 if mode == "created" else 200
            self._send_json(status, response)

        def _handle_list(self) -> None:
            host, port = self.server.server_address[:2]
            base = f"http://{host}:{port}"
            mode = state.list_mode

            if mode == "bad_json":
                self._send_raw(200, b"{", "application/json")
                return
            if mode == "bad_shape":
                self._send_json(200, {"value": "not-an-array"})
                return
            if mode == "http_error":
                self._send_json(503, {"error": {"code": "Unavailable"}})
                return
            if mode == "empty":
                self._send_json(200, {"value": [], "count": 0})
                return
            if mode == "one_page":
                self._send_json(
                    200,
                    {
                        "value": [{"name": "alphaSource", "kind": "AzureStorage"}],
                        "count": 1,
                    },
                )
                return
            if mode == "multi_unordered":
                self._send_json(
                    200,
                    {
                        "value": [
                            {"name": "zetaSource", "kind": "AzureStorage"},
                            {"name": "alphaSource", "kind": "AzureStorage"},
                        ],
                        "count": 2,
                    },
                )
                return
            if mode == "duplicate_names":
                self._send_json(
                    200,
                    {
                        "value": [
                            {"name": "alphaSource", "kind": "AzureStorage"},
                            {"name": "alphaSource", "kind": "AzureStorage"},
                        ],
                        "count": 2,
                    },
                )
                return
            if mode == "remote_state_mix":
                self._send_json(
                    200,
                    {
                        "value": [
                            {"name": "betaSource", "kind": "AdlsGen2"},
                            {"name": "alphaSource", "kind": "AzureStorage"},
                        ],
                        "count": 2,
                    },
                )
                return
            if mode == "paginated":
                query = parse_qs(urlparse(self.path).query)
                if query.get("page") == ["2"]:
                    self._send_json(
                        200,
                        {
                            "value": [{"name": "betaSource", "kind": "AdlsGen2"}],
                            "count": 1,
                        },
                    )
                    return
                self._send_json(
                    200,
                    {
                        "value": [{"name": "alphaSource", "kind": "AzureStorage"}],
                        "count": 99,
                        "nextLink": (
                            f"{base}/scan/datasources?api-version={SCANNING_API_VERSION}&page=2"
                        ),
                    },
                )
                return
            if mode == "relative_next":
                self._send_json(
                    200,
                    {
                        "value": [{"name": "alphaSource"}],
                        "nextLink": f"/scan/datasources?api-version={SCANNING_API_VERSION}&page=2",
                    },
                )
                return
            if mode == "cross_origin":
                self._send_json(
                    200,
                    {
                        "value": [{"name": "alphaSource"}],
                        "nextLink": (
                            f"https://evil.example/scan/datasources"
                            f"?api-version={SCANNING_API_VERSION}"
                        ),
                    },
                )
                return
            if mode == "loop_next":
                self._send_json(
                    200,
                    {
                        "value": [{"name": "alphaSource"}],
                        "nextLink": (
                            f"{base}/scan/datasources?api-version={SCANNING_API_VERSION}&loop=1"
                        ),
                    },
                )
                return

            self._send_json(500, {"error": {"code": "UnknownScenario"}})

        def _handle_get(self, name: str) -> None:
            if name in state.get_bodies:
                self._send_json(200, state.get_bodies[name])
                return

            mode = state.get_mode
            if mode == "not_found":
                self._send_json(404, {"error": {"code": "NotFound"}})
                return
            if mode == "bad_json":
                self._send_raw(200, b"not-json", "application/json")
                return
            if mode == "bad_shape":
                self._send_json(200, ["not", "an", "object"])
                return
            if mode == "identity_mismatch":
                self._send_json(
                    200,
                    azure_storage_fixture("otherSource"),
                )
                return
            if mode == "missing_name":
                body = azure_storage_fixture(name)
                del body["name"]
                self._send_json(200, body)
                return
            if mode == "missing_kind":
                body = azure_storage_fixture(name)
                del body["kind"]
                self._send_json(200, body)
                return
            if mode == "unsupported_kind":
                self._send_json(
                    200,
                    {
                        "name": name,
                        "kind": "AdlsGen2",
                        "creationType": "Manual",
                        "properties": {
                            "endpoint": "https://datalake.dfs.core.windows.net/",
                            "collection": {"referenceName": "root"},
                            "dataSourceCollectionMovingState": "Active",
                        },
                    },
                )
                return
            if mode == "unknown_field":
                body = azure_storage_fixture(name)
                body["unexpectedField"] = "x"
                self._send_json(200, body)
                return
            if mode == "sensitive":
                body = azure_storage_fixture(name)
                body["properties"]["accountKey"] = "SUPER-SECRET-VALUE-DO-NOT-LEAK"
                self._send_json(200, body)
                return
            if mode == "legacy_moving_zero":
                # Official Get example wire quirk — not Active.
                self._send_json(
                    200,
                    azure_storage_fixture(name, moving_state="0"),
                )
                return
            if mode == "scans_empty":
                self._send_json(
                    200,
                    azure_storage_fixture(name, omit_scans=False, include_scans=[]),
                )
                return
            if mode == "scans_nonempty":
                self._send_json(
                    200,
                    azure_storage_fixture(
                        name,
                        omit_scans=False,
                        include_scans=[{"name": "scan1", "kind": "AzureStorageMsi"}],
                    ),
                )
                return
            if mode == "auto_managed":
                self._send_json(
                    200,
                    azure_storage_fixture(name, creation_type="AutoManaged"),
                )
                return
            if mode == "moving":
                self._send_json(
                    200,
                    azure_storage_fixture(name, moving_state="Moving"),
                )
                return
            # Default success body is intentionally richer than the historical
            # minimal get fixture so remote-state capture can succeed in
            # remote_state-oriented contract tests. Legacy client get tests that
            # only assert kind/name continue to pass.
            self._send_json(
                200,
                azure_storage_fixture(
                    name,
                    include_timestamps=True,
                    observed={
                        "resourceGroup": "rg-example",
                        "subscriptionId": "00000000-0000-0000-0000-000000000001",
                        "location": "westus2",
                        "resourceName": "example",
                        "resourceId": (
                            "/subscriptions/00000000-0000-0000-0000-000000000001"
                            "/resourceGroups/rg-example/providers/Microsoft.Storage"
                            "/storageAccounts/example"
                        ),
                        "dataUseGovernance": "Disabled",
                    },
                ),
            )

    return PurviewContractHandler


@dataclass(frozen=True)
class ContractServer:
    host: str
    port: int
    state: ScenarioState

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def health_url(self) -> str:
        return f"{self.base_url}{HEALTH_PATH}"


@contextmanager
def start_contract_server(
    *,
    list_mode: str = "one_page",
    get_mode: str = "success",
    put_mode: str = "created",
    put_expected_body: dict[str, Any] | None = None,
    put_script: list[str] | None = None,
    get_bodies: dict[str, dict[str, Any]] | None = None,
) -> Iterator[ContractServer]:
    """Start an ephemeral loopback Purview contract server and guarantee teardown."""
    state = ScenarioState(
        list_mode=list_mode,
        get_mode=get_mode,
        put_mode=put_mode,
        put_expected_body=put_expected_body,
        put_script=list(put_script or []),
        get_bodies=dict(get_bodies or {}),
    )
    handler = _make_handler(state)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield ContractServer(host=str(host), port=int(port), state=state)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
