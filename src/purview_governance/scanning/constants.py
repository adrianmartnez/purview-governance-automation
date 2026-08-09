"""Scanning Data Plane constants (API version, timeouts, pagination bounds)."""

from __future__ import annotations

import httpx

SCANNING_API_VERSION = "2023-09-01"

CONNECT_TIMEOUT_SECONDS = 5.0
READ_TIMEOUT_SECONDS = 30.0
WRITE_TIMEOUT_SECONDS = 30.0
POOL_TIMEOUT_SECONDS = 5.0

MAX_LIST_PAGES = 50

DEFAULT_TIMEOUT = httpx.Timeout(
    CONNECT_TIMEOUT_SECONDS,
    connect=CONNECT_TIMEOUT_SECONDS,
    read=READ_TIMEOUT_SECONDS,
    write=WRITE_TIMEOUT_SECONDS,
    pool=POOL_TIMEOUT_SECONDS,
)
