"""Tests that credential-bearing field names are rejected with stable codes."""

from __future__ import annotations

import pytest

from purview_governance.config import ConfigValidationError, validate_config_text

BASE = {
    "apiVersion": "purview-governance-config/v1",
    "target": {"endpoint": "https://contoso-fictional.purview.azure.com"},
    "authentication": {"strategy": "defaultAzureCredential"},
    "resources": [],
}


@pytest.mark.parametrize(
    "field_name",
    [
        "clientSecret",
        "client_secret",
        "password",
        "accessToken",
        "privateKey",
        "connectionString",
    ],
)
def test_secret_field_names_rejected(field_name: str) -> None:
    import json

    document = dict(BASE)
    auth = dict(document["authentication"])
    auth[field_name] = "should-not-be-accepted"
    document["authentication"] = auth
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config_text(json.dumps(document), format_hint="json")
    diag = next(d for d in exc_info.value.diagnostics if field_name in d.path)
    assert diag.code == "config.secret_field_forbidden"
