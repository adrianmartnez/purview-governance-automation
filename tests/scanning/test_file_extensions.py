"""FileExtensionsType enum enforcement for config and remote normalize."""

from __future__ import annotations

import pytest

from purview_governance.config import validate_config_text
from purview_governance.config.diagnostics import ConfigValidationError
from purview_governance.remote_state.errors import RemoteStateError
from purview_governance.remote_state.scan_normalize import (
    normalize_custom_azure_storage_scan_ruleset_get,
)
from purview_governance.scanning.file_extensions import FILE_EXTENSIONS_TYPE

_CONFIG_TEMPLATE = """
apiVersion: purview-governance-config/v2
target:
  endpoint: https://account.purview.azure.com
authentication:
  strategy: defaultAzureCredential
resources:
  - type: scanRuleSet
    name: custom-rules
    kind: AzureStorage
    scanRulesetType: Custom
    properties:
      scanningRule:
        fileExtensions: [{extensions}]
      excludedSystemClassifications: []
      includedCustomClassificationRuleNames: []
"""


def _ruleset_body(extensions: list[str]) -> dict:
    return {
        "name": "custom-rules",
        "kind": "AzureStorage",
        "scanRulesetType": "Custom",
        "properties": {
            "scanningRule": {"fileExtensions": extensions},
            "excludedSystemClassifications": [],
            "includedCustomClassificationRuleNames": [],
        },
    }


def test_official_csv_json_accepted_in_config() -> None:
    config = validate_config_text(
        _CONFIG_TEMPLATE.format(extensions="CSV, JSON"),
        format_hint="yaml",
    )
    srs = config.resources[0]
    assert srs.file_extensions == ("CSV", "JSON")  # type: ignore[attr-defined]


def test_banana_rejected_in_config() -> None:
    with pytest.raises(ConfigValidationError) as exc:
        validate_config_text(
            _CONFIG_TEMPLATE.format(extensions="BANANA"),
            format_hint="yaml",
        )
    codes = {diagnostic.code for diagnostic in exc.value.diagnostics}
    assert "config.invalid_file_extension" in codes


def test_official_csv_json_accepted_in_remote() -> None:
    result = normalize_custom_azure_storage_scan_ruleset_get(
        _ruleset_body(["CSV", "JSON"]),
        requested_name="custom-rules",
    )
    assert result.file_extensions == ("CSV", "JSON")


def test_banana_rejected_in_remote() -> None:
    with pytest.raises(RemoteStateError) as exc:
        normalize_custom_azure_storage_scan_ruleset_get(
            _ruleset_body(["BANANA"]),
            requested_name="custom-rules",
        )
    assert exc.value.code == "remote_state.invalid_file_extension"


def test_file_extensions_type_contains_official_core_values() -> None:
    assert {"CSV", "JSON", "PARQUET", "PDF", "Documents"} <= FILE_EXTENSIONS_TYPE
    assert "BANANA" not in FILE_EXTENSIONS_TYPE
