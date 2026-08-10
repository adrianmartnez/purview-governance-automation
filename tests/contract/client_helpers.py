"""Test-only helpers to construct a loopback Scanning client."""

from __future__ import annotations

from purview_governance.auth import PurviewAuthorizationProvider
from purview_governance.scanning.client import PurviewScanningClient
from tests.auth.fakes import FakeTokenCredential
from tests.contract.server import AUTH_SENTINEL

DEFAULT_LOGICAL_TARGET = "https://account.purview.azure.com"


def make_loopback_client(
    base_url: str,
    *,
    logical_target_endpoint: str = DEFAULT_LOGICAL_TARGET,
    auth_provider: PurviewAuthorizationProvider | None = None,
) -> PurviewScanningClient:
    """Build a package client bound to a literal loopback HTTP contract server."""
    if auth_provider is None:
        token = AUTH_SENTINEL.removeprefix("Bearer ").strip()
        auth_provider = PurviewAuthorizationProvider(FakeTokenCredential(token))  # type: ignore[arg-type]
    return PurviewScanningClient._from_loopback_base_url(
        base_url,
        auth_provider,
        logical_target_endpoint=logical_target_endpoint,
    )
