"""Purview authorization header provider boundary."""

from __future__ import annotations

from azure.core.credentials import AccessToken, TokenCredential

from purview_governance.auth.errors import AuthenticationError
from purview_governance.auth.scopes import PURVIEW_DEFAULT_SCOPE


class PurviewAuthorizationProvider:
    """Acquire in-memory Bearer authorization for Purview using TokenCredential."""

    def __init__(
        self,
        credential: TokenCredential,
        *,
        scopes: tuple[str, ...] = (PURVIEW_DEFAULT_SCOPE,),
    ) -> None:
        self._credential = credential
        self._scopes = scopes

    def __repr__(self) -> str:
        return f"PurviewAuthorizationProvider(scopes={self._scopes!r})"

    def acquire_authorization_header(self) -> str:
        """Return ``Authorization`` header value ``Bearer <token>`` (in memory only)."""
        failed = False
        try:
            token: AccessToken = self._credential.get_token(*self._scopes)
        except Exception:
            # Do not retain the raw exception object or message. Raise only after
            # leaving the active except block so __context__ stays clear.
            failed = True
        if failed:
            raise AuthenticationError(
                "auth.token_acquisition_failed",
                "failed to acquire a Microsoft Entra token for Purview",
            )
        return f"Bearer {token.token}"
