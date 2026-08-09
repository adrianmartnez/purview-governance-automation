"""Deterministic TokenCredential fakes for offline tests (not packaged)."""

from __future__ import annotations

from azure.core.credentials import AccessToken, TokenCredential


class FakeTokenCredential:
    """Test double implementing the TokenCredential contract."""

    def __init__(
        self,
        token: str = "fake-token-value",
        *,
        expires_on: int = 9999999999,
        fail_with: BaseException | None = None,
    ) -> None:
        self._token = token
        self._expires_on = expires_on
        self._fail_with = fail_with
        self.calls: list[tuple[str, ...]] = []

    def get_token(self, *scopes: str, **kwargs: object) -> AccessToken:
        del kwargs  # unused; present for TokenCredential compatibility
        self.calls.append(scopes)
        if self._fail_with is not None:
            raise self._fail_with
        return AccessToken(self._token, self._expires_on)


def as_token_credential(fake: FakeTokenCredential) -> TokenCredential:
    """Widen fake type for callers typed against TokenCredential."""
    return fake  # type: ignore[return-value]
