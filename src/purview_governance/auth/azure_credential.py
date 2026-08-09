"""Production Microsoft Entra credential factory for Purview automation."""

from __future__ import annotations

from azure.identity import DefaultAzureCredential

from purview_governance.auth.provider import PurviewAuthorizationProvider


def create_default_azure_credential_provider() -> PurviewAuthorizationProvider:
    """Build a provider backed by DefaultAzureCredential (lazy construction).

    This is a convenient supported factory, not a claim of live Purview validation.
    Callers may instead inject any ``TokenCredential`` into
    ``PurviewAuthorizationProvider``.
    """
    credential = DefaultAzureCredential(
        exclude_interactive_browser_credential=True,
        logging_enable=False,
    )
    return PurviewAuthorizationProvider(credential)
