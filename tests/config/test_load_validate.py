"""Tests for configuration loading and validation diagnostics."""

from __future__ import annotations

import pytest

from purview_governance.config import (
    ConfigValidationError,
    validate_config_text,
)

VALID_JSON = """
{
  "apiVersion": "purview-governance-config/v1",
  "target": {"endpoint": "https://contoso-fictional.purview.azure.com"},
  "authentication": {"strategy": "defaultAzureCredential"},
  "resources": []
}
"""

VALID_YAML = """
apiVersion: purview-governance-config/v1
target:
  endpoint: https://contoso-fictional.purview.azure.com
authentication:
  strategy: defaultAzureCredential
resources: []
"""


def test_valid_json_config() -> None:
    config = validate_config_text(VALID_JSON, format_hint="json")
    assert config.target.endpoint == "https://contoso-fictional.purview.azure.com"


def test_valid_yaml_config() -> None:
    config = validate_config_text(VALID_YAML, format_hint="yaml")
    assert config.authentication.strategy == "defaultAzureCredential"


def test_malformed_json() -> None:
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config_text("{", format_hint="json")
    assert exc_info.value.diagnostics[0].code == "config.invalid_syntax"


def test_malformed_yaml() -> None:
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config_text(":\n  -", format_hint="yaml")
    assert exc_info.value.diagnostics[0].code == "config.invalid_syntax"


def test_unsupported_contract_version() -> None:
    text = VALID_JSON.replace("purview-governance-config/v1", "purview-governance-config/v99")
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config_text(text, format_hint="json")
    codes = {d.code for d in exc_info.value.diagnostics}
    assert "config.unsupported_version" in codes


def test_unknown_top_level_field() -> None:
    text = VALID_JSON.replace(
        '"resources": []',
        '"resources": [], "unexpectedField": true',
    )
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config_text(text, format_hint="json")
    diag = next(d for d in exc_info.value.diagnostics if d.path.endswith("unexpectedField"))
    assert diag.code == "config.unknown_field"


def test_unknown_nested_field() -> None:
    text = VALID_JSON.replace(
        '"endpoint": "https://contoso-fictional.purview.azure.com"',
        '"endpoint": "https://contoso-fictional.purview.azure.com", "region": "eastus"',
    )
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config_text(text, format_hint="json")
    diag = next(d for d in exc_info.value.diagnostics if d.path.endswith("region"))
    assert diag.code == "config.unknown_field"


def test_supported_data_source_resource_accepted() -> None:
    text = VALID_JSON.replace(
        '"resources": []',
        """
        "resources": [{
          "type": "dataSource",
          "name": "example-azure-storage",
          "kind": "AzureStorage",
          "properties": {
            "endpoint": "https://azurestorage.core.windows.net/",
            "collection": {"referenceName": "Collection-rZX"}
          }
        }]
        """,
    )
    config = validate_config_text(text, format_hint="json")
    assert len(config.resources) == 1
    assert config.resources[0].name == "example-azure-storage"


def test_unsupported_data_source_kind_rejected() -> None:
    text = VALID_JSON.replace(
        '"resources": []',
        """
        "resources": [{
          "type": "dataSource",
          "name": "example-azure-storage",
          "kind": "AdlsGen2",
          "properties": {
            "endpoint": "https://datalake.dfs.core.windows.net/",
            "collection": {"referenceName": "root"}
          }
        }]
        """,
    )
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config_text(text, format_hint="json")
    codes = {d.code for d in exc_info.value.diagnostics}
    assert "config.unsupported_data_source_kind" in codes


def test_duplicate_data_source_names_rejected() -> None:
    text = VALID_JSON.replace(
        '"resources": []',
        """
        "resources": [
          {
            "type": "dataSource",
            "name": "example-azure-storage",
            "kind": "AzureStorage",
            "properties": {
              "endpoint": "https://a.blob.core.windows.net/",
              "collection": {"referenceName": "root"}
            }
          },
          {
            "type": "dataSource",
            "name": "example-azure-storage",
            "kind": "AzureStorage",
            "properties": {
              "endpoint": "https://b.blob.core.windows.net/",
              "collection": {"referenceName": "root"}
            }
          }
        ]
        """,
    )
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config_text(text, format_hint="json")
    codes = {d.code for d in exc_info.value.diagnostics}
    assert "config.duplicate_data_source_name" in codes


def test_unknown_resource_field_rejected() -> None:
    text = VALID_JSON.replace(
        '"resources": []',
        """
        "resources": [{
          "type": "dataSource",
          "name": "example-azure-storage",
          "kind": "AzureStorage",
          "properties": {
            "endpoint": "https://azurestorage.core.windows.net/",
            "collection": {"referenceName": "Collection-rZX"}
          },
          "extra": true
        }]
        """,
    )
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config_text(text, format_hint="json")
    assert any(d.code == "config.unknown_field" for d in exc_info.value.diagnostics)


def test_invalid_endpoint_scheme() -> None:
    text = VALID_JSON.replace("https://", "http://")
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config_text(text, format_hint="json")
    assert any(d.code == "config.invalid_endpoint" for d in exc_info.value.diagnostics)


def test_invalid_endpoint_query_and_fragment() -> None:
    text = VALID_JSON.replace(
        "https://contoso-fictional.purview.azure.com",
        "https://contoso-fictional.purview.azure.com?x=1#frag",
    )
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config_text(text, format_hint="json")
    assert any(d.code == "config.invalid_endpoint" for d in exc_info.value.diagnostics)


def test_diagnostic_ordering_is_stable() -> None:
    text = """
    {
      "apiVersion": "purview-governance-config/v1",
      "zzz": 1,
      "aaa": 2,
      "target": {"endpoint": "https://contoso-fictional.purview.azure.com"},
      "authentication": {"strategy": "defaultAzureCredential"},
      "resources": []
    }
    """
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config_text(text, format_hint="json")
    paths = [d.path for d in exc_info.value.diagnostics]
    assert paths == sorted(paths)


def test_unsafe_yaml_tags_rejected() -> None:
    payload = "!!python/object/apply:os.system ['echo pwned']\n"
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config_text(payload, format_hint="yaml")
    assert exc_info.value.diagnostics[0].code == "config.invalid_syntax"
