"""Offline HTTP harness compatibility shim for the api-contract-tests lane.

The Purview-specific deterministic contract server lives in
``tests.contract.server``. This module keeps the historical
``start_local_harness`` name for readiness smoke tests.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from tests.contract.server import (
    HEALTH_PATH,
    HEALTH_PAYLOAD,
    ContractServer,
    start_contract_server,
)

__all__ = [
    "HEALTH_PATH",
    "HEALTH_PAYLOAD",
    "LocalHarness",
    "start_local_harness",
]


# Back-compat alias used by readiness tests.
LocalHarness = ContractServer


@contextmanager
def start_local_harness() -> Iterator[ContractServer]:
    """Start the deterministic loopback contract server (health + Purview routes)."""
    with start_contract_server() as server:
        yield server
