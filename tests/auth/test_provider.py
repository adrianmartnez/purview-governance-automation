"""Tests for PurviewAuthorizationProvider success path."""

from __future__ import annotations

from purview_governance.auth import PURVIEW_DEFAULT_SCOPE, PurviewAuthorizationProvider
from tests.auth.fakes import FakeTokenCredential


def test_fake_credential_success_scope_and_header() -> None:
    fake = FakeTokenCredential(token="unit-test-token")
    provider = PurviewAuthorizationProvider(fake)  # type: ignore[arg-type]
    header = provider.acquire_authorization_header()
    assert header == "Bearer unit-test-token"
    assert fake.calls == [(PURVIEW_DEFAULT_SCOPE,)]
    assert PURVIEW_DEFAULT_SCOPE == "https://purview.azure.net/.default"


def test_exactly_one_token_acquisition_per_header_call() -> None:
    fake = FakeTokenCredential(token="once")
    provider = PurviewAuthorizationProvider(fake)  # type: ignore[arg-type]
    provider.acquire_authorization_header()
    provider.acquire_authorization_header()
    assert len(fake.calls) == 2
    assert all(call == (PURVIEW_DEFAULT_SCOPE,) for call in fake.calls)


def test_provider_repr_does_not_include_token() -> None:
    fake = FakeTokenCredential(token="secret-token-should-not-appear")
    provider = PurviewAuthorizationProvider(fake)  # type: ignore[arg-type]
    provider.acquire_authorization_header()
    assert "secret-token-should-not-appear" not in repr(provider)
