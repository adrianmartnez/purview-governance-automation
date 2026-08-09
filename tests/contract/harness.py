"""Offline HTTP harness for the api-contract-tests lane readiness check.

This module is test infrastructure only. It does not emulate Microsoft Purview
APIs; issue #11 will introduce the Purview-specific contract-test server.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HEALTH_PATH = "/health"
HEALTH_PAYLOAD = {"status": "ok", "lane": "api-contract-tests"}


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 — stdlib handler API
        if self.path != HEALTH_PATH:
            self.send_error(404)
            return
        body = json.dumps(HEALTH_PAYLOAD).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return


@dataclass(frozen=True)
class LocalHarness:
    host: str
    port: int

    @property
    def health_url(self) -> str:
        return f"http://{self.host}:{self.port}{HEALTH_PATH}"


@contextmanager
def start_local_harness() -> Iterator[LocalHarness]:
    """Start an ephemeral loopback HTTP server and guarantee teardown."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _HealthHandler)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield LocalHarness(host=str(host), port=int(port))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
