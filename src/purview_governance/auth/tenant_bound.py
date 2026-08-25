"""Tenant-bound authorization for controlled Unified Catalog apply/v3."""

from __future__ import annotations

from dataclasses import dataclass

from azure.core.credentials import AccessToken, TokenCredential
from azure.identity import (
    AzureCliCredential,
    AzureDeveloperCliCredential,
    CertificateCredential,
    ClientSecretCredential,
    DefaultAzureCredential,
    ManagedIdentityCredential,
)

from purview_governance.auth.errors import AuthenticationError
from purview_governance.auth.provider import PurviewAuthorizationProvider
from purview_governance.auth.scopes import PURVIEW_DEFAULT_SCOPE
from purview_governance.uuid_utils import require_uuid_string

UNSUPPORTED_CREDENTIAL_TYPES = (
    ManagedIdentityCredential,
    DefaultAzureCredential,
)

SUPPORTED_TENANT_AWARE_CREDENTIAL_TYPES = (
    ClientSecretCredential,
    CertificateCredential,
    AzureCliCredential,
    AzureDeveloperCliCredential,
)


class TenantBindingUnsupportedError(Exception):
    """Raised when APPLY/v3 cannot establish tenant-aware execution binding."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class TenantBoundExecutionContext:
    execution_tenant_id: str
    execution_target_context_identity: str
    endpoint: str


class TenantBoundAuthorizationProvider(PurviewAuthorizationProvider):
    """Allowlisted tenant-aware Purview authorization for APPLY/v3."""

    def __init__(
        self,
        credential: TokenCredential,
        *,
        tenant_id: str,
        endpoint: str,
        surface: str = "unifiedCatalog",
        scopes: tuple[str, ...] = (PURVIEW_DEFAULT_SCOPE,),
    ) -> None:
        if isinstance(credential, UNSUPPORTED_CREDENTIAL_TYPES):
            raise TenantBindingUnsupportedError(
                "apply.tenant_binding_unsupported",
                "credential type is not tenant-aware for APPLY/v3",
            )
        if not isinstance(credential, SUPPORTED_TENANT_AWARE_CREDENTIAL_TYPES):
            raise TenantBindingUnsupportedError(
                "apply.tenant_binding_unsupported",
                "credential type is not on the APPLY/v3 allowlist",
            )
        self._execution_tenant_id = require_uuid_string(tenant_id, field_label="tenantId")
        self._endpoint = endpoint
        self._surface = surface
        super().__init__(credential, scopes=scopes)

    @property
    def execution_tenant_id(self) -> str:
        return self._execution_tenant_id

    @property
    def execution_target_context_identity(self) -> str:
        from purview_governance.plan.identity import compute_target_context_identity_v3

        return compute_target_context_identity_v3(
            surface=self._surface,
            tenant_id=self._execution_tenant_id,
            endpoint=self._endpoint,
        )

    def acquire_authorization_header(self) -> str:
        token = self._acquire_access_token()
        return f"Bearer {token.token}"

    def _acquire_access_token(self) -> AccessToken:
        failed = False
        try:
            token = self._credential.get_token(
                *self._scopes,
                tenant_id=self._execution_tenant_id,
            )
        except Exception:
            failed = True
        if failed:
            raise AuthenticationError(
                "auth.token_acquisition_failed",
                "failed to acquire a Microsoft Entra token for Purview",
            )
        return token

    def execution_context(self) -> TenantBoundExecutionContext:
        return TenantBoundExecutionContext(
            execution_tenant_id=self._execution_tenant_id,
            execution_target_context_identity=self.execution_target_context_identity,
            endpoint=self._endpoint,
        )


def is_tenant_bound_provider(auth_provider: PurviewAuthorizationProvider) -> bool:
    return isinstance(auth_provider, TenantBoundAuthorizationProvider)
