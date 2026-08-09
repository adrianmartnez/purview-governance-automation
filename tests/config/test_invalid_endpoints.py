"""Invalid endpoint inputs must surface as ConfigValidationError only."""

from __future__ import annotations

import pytest

from purview_governance.config import ConfigValidationError, validate_config_text
from purview_governance.config.normalize import normalize_endpoint


def _json_with_endpoint(endpoint: str) -> str:
    return f"""
{{
  "apiVersion": "purview-governance-config/v1",
  "target": {{"endpoint": "{endpoint}"}},
  "authentication": {{"strategy": "defaultAzureCredential"}},
  "resources": []
}}
"""


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://example.com:abc",
        "https://example.com:99999",
        "https://[::1",
    ],
)
def test_malformed_endpoint_is_config_validation_error(endpoint: str) -> None:
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config_text(_json_with_endpoint(endpoint), format_hint="json")
    assert all(d.code == "config.invalid_endpoint" for d in exc_info.value.diagnostics)
    assert all(d.path == "/target/endpoint" for d in exc_info.value.diagnostics)


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://example.com:abc",
        "https://example.com:99999",
        "https://[::1",
    ],
)
def test_normalize_endpoint_never_raises_value_error(endpoint: str) -> None:
    with pytest.raises(ConfigValidationError) as exc_info:
        normalize_endpoint(endpoint)
    assert exc_info.value.diagnostics[0].code == "config.invalid_endpoint"
    assert not isinstance(exc_info.value.__cause__, ValueError)


def test_valid_explicit_port_is_preserved() -> None:
    assert (
        normalize_endpoint("https://contoso-fictional.purview.azure.com:443/")
        == "https://contoso-fictional.purview.azure.com:443"
    )
