"""Offline wiring tests for DefaultAzureCredential factory."""

from __future__ import annotations

from typing import Any

import pytest

import purview_governance.auth.azure_credential as azure_credential_module
from purview_governance.auth import PurviewAuthorizationProvider


def test_default_credential_lazy_and_safe_kwargs(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    class SpyCredential:
        def __init__(self, **kwargs: Any) -> None:
            calls.append(kwargs)

        def get_token(self, *scopes: str, **kwargs: Any) -> Any:
            raise AssertionError("get_token must not be called in wiring tests")

    monkeypatch.setattr(azure_credential_module, "DefaultAzureCredential", SpyCredential)
    assert calls == []

    provider = azure_credential_module.create_default_azure_credential_provider()
    assert isinstance(provider, PurviewAuthorizationProvider)
    assert len(calls) == 1
    assert calls[0]["exclude_interactive_browser_credential"] is True
    assert calls[0]["logging_enable"] is False


def test_modules_import_without_constructing_default_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(**kwargs: Any) -> Any:
        raise AssertionError(f"DefaultAzureCredential must not run at import: {kwargs}")

    monkeypatch.setattr(azure_credential_module, "DefaultAzureCredential", _boom)
    import importlib

    import purview_governance.auth as auth_pkg

    importlib.reload(auth_pkg)
    # Accessing exported factory must still be lazy until called.
    assert callable(auth_pkg.create_default_azure_credential_provider)
