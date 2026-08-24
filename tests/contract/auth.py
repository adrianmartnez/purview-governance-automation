"""Shared contract-test authorization helpers (test-only)."""

from __future__ import annotations

AUTH_SENTINEL = "Bearer TEST_PURVIEW_AUTH_SENTINEL"


def authorization_is_valid(header: str | None) -> bool:
    """Return whether the Authorization header matches the contract sentinel."""
    return header == AUTH_SENTINEL


def authorization_present(header: str | None) -> bool:
    """Return whether any Authorization header was provided."""
    return bool(header)
