"""Tests that duplicate keys are rejected (never last-value-wins)."""

from __future__ import annotations

import pytest

from purview_governance.config import ConfigValidationError, validate_config_text


def test_duplicate_root_key_json() -> None:
    text = """
    {
      "apiVersion": "purview-governance-config/v1",
      "apiVersion": "purview-governance-config/v1",
      "target": {"endpoint": "https://contoso-fictional.purview.azure.com"},
      "authentication": {"strategy": "defaultAzureCredential"},
      "resources": []
    }
    """
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config_text(text, format_hint="json")
    assert any(d.code == "config.duplicate_key" for d in exc_info.value.diagnostics)


def test_duplicate_nested_key_json_does_not_last_value_win() -> None:
    text = """
    {
      "apiVersion": "purview-governance-config/v1",
      "target": {
        "endpoint": "https://first.example.com",
        "endpoint": "https://second.example.com"
      },
      "authentication": {"strategy": "defaultAzureCredential"},
      "resources": []
    }
    """
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config_text(text, format_hint="json")
    assert any(d.code == "config.duplicate_key" for d in exc_info.value.diagnostics)
    # Ensure we did not silently accept the second endpoint.
    with pytest.raises(ConfigValidationError):
        validate_config_text(text, format_hint="json")


def test_duplicate_root_key_yaml() -> None:
    text = """
apiVersion: purview-governance-config/v1
apiVersion: purview-governance-config/v1
target:
  endpoint: https://contoso-fictional.purview.azure.com
authentication:
  strategy: defaultAzureCredential
resources: []
"""
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config_text(text, format_hint="yaml")
    assert any(d.code == "config.duplicate_key" for d in exc_info.value.diagnostics)


def test_duplicate_nested_key_yaml_does_not_last_value_win() -> None:
    text = """
apiVersion: purview-governance-config/v1
target:
  endpoint: https://first.example.com
  endpoint: https://second.example.com
authentication:
  strategy: defaultAzureCredential
resources: []
"""
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config_text(text, format_hint="yaml")
    assert any(d.code == "config.duplicate_key" for d in exc_info.value.diagnostics)
