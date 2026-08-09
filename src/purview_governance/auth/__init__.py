"""Microsoft Entra authentication boundary for Purview integration."""

from purview_governance.auth.azure_credential import create_default_azure_credential_provider
from purview_governance.auth.errors import AuthenticationError
from purview_governance.auth.provider import PurviewAuthorizationProvider
from purview_governance.auth.scopes import PURVIEW_DEFAULT_SCOPE

__all__ = [
    "PURVIEW_DEFAULT_SCOPE",
    "AuthenticationError",
    "PurviewAuthorizationProvider",
    "create_default_azure_credential_provider",
]
