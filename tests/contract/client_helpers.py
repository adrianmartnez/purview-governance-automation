"""Test-only helpers to construct a loopback Scanning client."""

from __future__ import annotations

from purview_governance.auth import PurviewAuthorizationProvider
from purview_governance.scanning.client import PurviewScanningClient
from tests.auth.fakes import FakeTokenCredential
from tests.contract.server import AUTH_SENTINEL


def make_loopback_client(base_url: str) -> PurviewScanningClient:
    """Build a package client bound to a literal loopback HTTP contract server."""
    token = AUTH_SENTINEL.removeprefix("Bearer ").strip()
    provider = PurviewAuthorizationProvider(FakeTokenCredential(token))  # type: ignore[arg-type]
    return PurviewScanningClient._from_loopback_base_url(base_url, provider)
