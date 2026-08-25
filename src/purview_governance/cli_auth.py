"""Package-private CLI authentication helpers (not a public surface)."""

from __future__ import annotations

import os

from azure.core.credentials import AccessToken, TokenCredential
from azure.identity import (
    AzureCliCredential,
    AzureDeveloperCliCredential,
    CertificateCredential,
    ClientSecretCredential,
)

from purview_governance.auth.errors import AuthenticationError
from purview_governance.auth.provider import PurviewAuthorizationProvider

CREDENTIAL_SELECTORS = (
    "azure-cli",
    "azure-developer-cli",
    "client-secret",
    "certificate",
)


class _CliCredentialMaterialError(Exception):
    """Missing or unsupported credential material for a CLI selector."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class _SentinelTokenCredential:
    """TokenCredential stub that refuses every acquisition attempt."""

    def get_token(self, *scopes: str, **kwargs: object) -> AccessToken:
        raise AuthenticationError(
            "cli.token_acquisition_forbidden",
            "token acquisition is forbidden for this CLI path",
        )


class _SentinelAuthorizationProvider(PurviewAuthorizationProvider):
    """No-token provider for blocked apply (raises if header/token is requested)."""

    def __init__(self) -> None:
        super().__init__(_SentinelTokenCredential())  # type: ignore[arg-type]

    def acquire_authorization_header(self) -> str:
        raise AuthenticationError(
            "cli.token_acquisition_forbidden",
            "token acquisition is forbidden for this CLI path",
        )


def _build_azure_credential(selector: str, *, tenant_id: str) -> TokenCredential:
    """Build an azure.identity credential; tenant always from caller (never AZURE_TENANT_ID)."""
    if selector == "azure-cli":
        return AzureCliCredential(tenant_id=tenant_id)
    if selector == "azure-developer-cli":
        return AzureDeveloperCliCredential(tenant_id=tenant_id)
    if selector == "client-secret":
        client_id = os.environ.get("AZURE_CLIENT_ID")
        client_secret = os.environ.get("AZURE_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise _CliCredentialMaterialError("cli.credential_material_missing")
        return ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        )
    if selector == "certificate":
        client_id = os.environ.get("AZURE_CLIENT_ID")
        certificate_path = os.environ.get("AZURE_CLIENT_CERTIFICATE_PATH")
        if not client_id or not certificate_path:
            raise _CliCredentialMaterialError("cli.credential_material_missing")
        password = os.environ.get("AZURE_CLIENT_CERTIFICATE_PASSWORD")
        if password is not None:
            return CertificateCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                certificate_path=certificate_path,
                password=password,
            )
        return CertificateCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            certificate_path=certificate_path,
        )
    raise _CliCredentialMaterialError("cli.credential_unsupported")
