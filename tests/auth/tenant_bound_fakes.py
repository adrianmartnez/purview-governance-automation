"""Offline tenant-aware credentials for APPLY/v3 contract tests."""

from __future__ import annotations

from azure.core.credentials import AccessToken
from azure.identity import ClientSecretCredential


class OfflineClientSecretCredential(ClientSecretCredential):
    """Allowlisted credential that never contacts Microsoft Entra."""

    def __init__(self, token: str = "offline-contract-token") -> None:
        self._offline_token = token

    def get_token(self, *scopes: str, **kwargs: object) -> AccessToken:
        del scopes, kwargs
        return AccessToken(self._offline_token, 9999999999)
