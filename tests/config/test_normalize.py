"""Tests for deterministic configuration normalization."""

from __future__ import annotations

from purview_governance.config import to_canonical_json, validate_config_text

JSON_DOC = """
{
  "apiVersion": "purview-governance-config/v1",
  "target": {"endpoint": "https://Contoso-Fictional.Purview.Azure.com/"},
  "authentication": {"strategy": "defaultAzureCredential"},
  "resources": []
}
"""

YAML_DOC = """
apiVersion: purview-governance-config/v1
target:
  endpoint: "https://Contoso-Fictional.Purview.Azure.com/"
authentication:
  strategy: defaultAzureCredential
resources: []
"""


def test_endpoint_canonicalization_strips_trailing_slash_and_lowercases_host() -> None:
    config = validate_config_text(JSON_DOC, format_hint="json")
    assert config.target.endpoint == "https://contoso-fictional.purview.azure.com"


def test_yaml_and_json_normalize_identically() -> None:
    from_json = validate_config_text(JSON_DOC, format_hint="json")
    from_yaml = validate_config_text(YAML_DOC, format_hint="yaml")
    assert to_canonical_json(from_json) == to_canonical_json(from_yaml)


def test_empty_resources_remain_canonically_stable() -> None:
    config = validate_config_text(JSON_DOC, format_hint="json")
    assert config.resources == ()
    assert '"resources":[]' in to_canonical_json(config)


def test_resources_ordered_by_name_in_normalized_config() -> None:
    text = """
{
  "apiVersion": "purview-governance-config/v1",
  "target": {"endpoint": "https://contoso-fictional.purview.azure.com"},
  "authentication": {"strategy": "defaultAzureCredential"},
  "resources": [
    {
      "type": "dataSource",
      "name": "zetaSource",
      "kind": "AzureStorage",
      "properties": {
        "endpoint": "https://zeta.blob.core.windows.net/",
        "collection": {"referenceName": "root"}
      }
    },
    {
      "type": "dataSource",
      "name": "alphaSource",
      "kind": "AzureStorage",
      "properties": {
        "endpoint": "https://alpha.blob.core.windows.net/",
        "collection": {"referenceName": "root"}
      }
    }
  ]
}
"""
    config = validate_config_text(text, format_hint="json")
    assert [item.name for item in config.resources] == ["alphaSource", "zetaSource"]
