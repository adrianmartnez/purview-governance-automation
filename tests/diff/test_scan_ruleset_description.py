"""Scan rule set description None vs empty-string diff encoding."""

from __future__ import annotations

from purview_governance.config import validate_config_text
from purview_governance.desired.models import DesiredState, ScanRuleSetDesiredState
from purview_governance.diff import diff_desired_vs_remote
from purview_governance.plan import build_governance_plan_v2
from purview_governance.remote_state.canonical import canonical_json_scalar
from purview_governance.remote_state.models import NormalizedScanRuleSet, build_remote_state_v2
from purview_governance.remote_state.scan_normalize import (
    normalize_custom_azure_storage_scan_ruleset_get,
)

_CONFIG_V2 = """
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
        fileExtensions: [CSV, JSON]
      excludedSystemClassifications: []
      includedCustomClassificationRuleNames: []
"""


def _desired(*, description: str | None) -> ScanRuleSetDesiredState:
    return ScanRuleSetDesiredState(
        name="custom-rules",
        kind="AzureStorage",
        scan_ruleset_type="Custom",
        file_extensions=("CSV", "JSON"),
        excluded_system_classifications=(),
        included_custom_classification_rule_names=(),
        description=description,
    )


def _remote(*, description: str | None) -> NormalizedScanRuleSet:
    return NormalizedScanRuleSet(
        name="custom-rules",
        kind="AzureStorage",
        scan_ruleset_type="Custom",
        file_extensions=("CSV", "JSON"),
        excluded_system_classifications=(),
        included_custom_classification_rule_names=(),
        description=description,
    )


def _diff_item(desired_description: str | None, remote_description: str | None):
    desired = DesiredState(
        data_sources=(), scan_rule_sets=(_desired(description=desired_description),)
    )
    remote = build_remote_state_v2(
        (),
        (),
        (),
        (),
        (),
        (),
        (_remote(description=remote_description),),
        (),
    )
    doc = diff_desired_vs_remote(desired, remote)
    assert len(doc.items) == 1
    return doc.items[0]


def _config_with_description(description: str | None):
    text = _CONFIG_V2
    if description is not None:
        # YAML empty string must be quoted to remain a string.
        rendered = '""' if description == "" else description
        text = text + f"      description: {rendered}\n"
    return validate_config_text(text, format_hint="yaml")


def _plan_self_validates(desired_description: str | None, remote_description: str | None) -> None:
    config = _config_with_description(desired_description)
    remote = build_remote_state_v2(
        (),
        (),
        (),
        (),
        (),
        (),
        (_remote(description=remote_description),),
        (),
    )
    plan = build_governance_plan_v2(config, remote)
    assert plan.api_version == "purview-governance-plan/v2"


def test_remote_none_desired_none_is_noop() -> None:
    item = _diff_item(None, None)
    assert item.outcome == "no-op"
    assert item.reasons == ()


def test_remote_empty_desired_empty_is_noop() -> None:
    item = _diff_item("", "")
    assert item.outcome == "no-op"
    assert item.reasons == ()


def test_remote_none_desired_empty_is_replace_and_plan_validates() -> None:
    item = _diff_item("", None)
    assert item.outcome == "replace"
    assert len(item.reasons) == 1
    reason = item.reasons[0]
    assert reason.code == "properties.description.changed"
    assert reason.before == canonical_json_scalar(None)
    assert reason.after == canonical_json_scalar("")
    assert reason.before == "null"
    assert reason.after == '""'
    _plan_self_validates("", None)


def test_remote_empty_desired_none_is_replace_and_plan_validates() -> None:
    item = _diff_item(None, "")
    assert item.outcome == "replace"
    reason = item.reasons[0]
    assert reason.before == '""'
    assert reason.after == "null"
    _plan_self_validates(None, "")


def test_distinct_strings_replace_valid() -> None:
    item = _diff_item("after", "before")
    assert item.outcome == "replace"
    reason = item.reasons[0]
    assert reason.before == canonical_json_scalar("before")
    assert reason.after == canonical_json_scalar("after")
    _plan_self_validates("after", "before")


def test_remote_normalize_preserves_empty_description() -> None:
    body = {
        "name": "custom-rules",
        "kind": "AzureStorage",
        "scanRulesetType": "Custom",
        "properties": {
            "scanningRule": {"fileExtensions": ["CSV", "JSON"]},
            "excludedSystemClassifications": [],
            "includedCustomClassificationRuleNames": [],
            "description": "",
        },
    }
    result = normalize_custom_azure_storage_scan_ruleset_get(body, requested_name="custom-rules")
    assert result.description == ""
