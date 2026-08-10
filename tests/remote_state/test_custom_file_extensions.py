"""customFileExtensions unsupported evidence on Custom AzureStorage SRS."""

from __future__ import annotations

from purview_governance.desired.models import DesiredState, ScanRuleSetDesiredState
from purview_governance.diff import diff_desired_vs_remote
from purview_governance.remote_state.canonical import compute_value_identity
from purview_governance.remote_state.models import build_remote_state_v2
from purview_governance.remote_state.scan_normalize import (
    normalize_custom_azure_storage_scan_ruleset_get,
)


def _base_body(**scanning_rule_extra):
    scanning_rule = {"fileExtensions": ["CSV", "JSON"]}
    scanning_rule.update(scanning_rule_extra)
    return {
        "name": "custom-rules",
        "kind": "AzureStorage",
        "scanRulesetType": "Custom",
        "properties": {
            "scanningRule": scanning_rule,
            "excludedSystemClassifications": [],
            "includedCustomClassificationRuleNames": [],
        },
    }


def test_absent_custom_file_extensions_ok() -> None:
    result = normalize_custom_azure_storage_scan_ruleset_get(
        _base_body(),
        requested_name="custom-rules",
    )
    assert result.unsupported_configurable_fields == ()


def test_null_custom_file_extensions_safe_absent() -> None:
    result = normalize_custom_azure_storage_scan_ruleset_get(
        _base_body(customFileExtensions=None),
        requested_name="custom-rules",
    )
    assert result.unsupported_configurable_fields == ()


def test_explicit_empty_array_is_unsupported_not_absent() -> None:
    result = normalize_custom_azure_storage_scan_ruleset_get(
        _base_body(customFileExtensions=[]),
        requested_name="custom-rules",
    )
    assert len(result.unsupported_configurable_fields) == 1
    field = result.unsupported_configurable_fields[0]
    assert field.path == "/properties/scanningRule/customFileExtensions"
    assert field.value_identity == compute_value_identity([])


def test_explicit_array_blocks_diff() -> None:
    custom = [
        {
            "fileExtension": ".log",
            "enabled": True,
            "customFileType": {"builtInType": "TXT"},
        }
    ]
    remote_srs = normalize_custom_azure_storage_scan_ruleset_get(
        _base_body(customFileExtensions=custom),
        requested_name="custom-rules",
    )
    desired = DesiredState(
        data_sources=(),
        scan_rule_sets=(
            ScanRuleSetDesiredState(
                name="custom-rules",
                kind="AzureStorage",
                scan_ruleset_type="Custom",
                file_extensions=("CSV", "JSON"),
                excluded_system_classifications=(),
                included_custom_classification_rule_names=(),
            ),
        ),
    )
    remote = build_remote_state_v2((), (), (), (), (remote_srs,), ())
    item = diff_desired_vs_remote(desired, remote).items[0]
    assert item.outcome == "blocked"
    assert any(
        reason.code == "remote.unsupported_configurable_field"
        and reason.path == "/properties/scanningRule/customFileExtensions"
        for reason in item.reasons
    )
