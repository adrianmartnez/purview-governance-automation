"""Payload builders and composite Scan identity for apply v2."""

from __future__ import annotations

import pytest

from purview_governance.apply.errors import ApplyValidationError
from purview_governance.apply.payloads import (
    azure_storage_msi_scan_put_payload,
    azure_storage_put_payload,
    custom_azure_storage_scan_ruleset_put_payload,
    custom_classification_rule_put_payload,
    materialize_mutation_intents,
    materialize_mutation_intents_v2,
)
from purview_governance.config import validate_config_text
from purview_governance.desired.models import (
    ClassificationRuleDesiredState,
    DataSourceDesiredState,
    RegexClassificationPatternDesired,
    ScanDesiredState,
    ScanRuleSetDesiredState,
)
from purview_governance.plan import build_governance_plan, build_governance_plan_v2
from purview_governance.remote_state.models import build_remote_state_v2
from tests.plan.helpers import create_config, empty_remote

_MULTI = """
apiVersion: purview-governance-config/v2
target:
  endpoint: https://account.purview.azure.com
authentication:
  strategy: defaultAzureCredential
resources:
  - type: dataSource
    name: ds-a
    kind: AzureStorage
    properties:
      endpoint: https://a.blob.core.windows.net/
      collection:
        referenceName: root
  - type: dataSource
    name: ds-b
    kind: AzureStorage
    properties:
      endpoint: https://b.blob.core.windows.net/
      collection:
        referenceName: root
  - type: classificationRule
    name: custom-rule
    kind: Custom
    properties:
      classificationName: Contoso.Secret
      minimumPercentageMatch: 80.0
      ruleStatus: Enabled
      dataPatterns:
        - kind: Regex
          pattern: "^[0-9]+$"
      columnPatterns:
        - kind: Regex
          pattern: "^col$"
  - type: scanRuleSet
    name: custom-srs
    kind: AzureStorage
    scanRulesetType: Custom
    properties:
      scanningRule:
        fileExtensions: [CSV, JSON]
      excludedSystemClassifications: []
      includedCustomClassificationRuleNames: [custom-rule]
  - type: scan
    name: DailyScan
    kind: AzureStorageMsi
    properties:
      dataSourceName: ds-a
      scanRulesetName: custom-srs
      scanRulesetType: Custom
      collection:
        referenceName: root
  - type: scan
    name: DailyScan
    kind: AzureStorageMsi
    properties:
      dataSourceName: ds-b
      scanRulesetName: AzureStorage
      scanRulesetType: System
      collection:
        referenceName: root
"""


def test_data_source_v1_and_v2_payload_equivalence() -> None:
    desired = DataSourceDesiredState(
        name="example-source",
        kind="AzureStorage",
        endpoint="https://example.blob.core.windows.net/",
        collection_reference_name="root",
    )
    assert azure_storage_put_payload(desired) == {
        "kind": "AzureStorage",
        "properties": {
            "collection": {"referenceName": "root"},
            "endpoint": "https://example.blob.core.windows.net/",
        },
    }
    plan_v1 = build_governance_plan(create_config(), empty_remote())
    intents_v1 = materialize_mutation_intents(plan_v1)
    remote_v2 = build_remote_state_v2((), (), (), (), (), (), (), ())
    config_v2 = validate_config_text(
        """
apiVersion: purview-governance-config/v2
target:
  endpoint: https://account.purview.azure.com
authentication:
  strategy: defaultAzureCredential
resources:
  - type: dataSource
    name: example-source
    kind: AzureStorage
    properties:
      endpoint: https://example.blob.core.windows.net/
      collection:
        referenceName: root
""",
        format_hint="yaml",
    )
    plan_v2 = build_governance_plan_v2(config_v2, remote_v2)
    intents_v2 = materialize_mutation_intents_v2(plan_v2)
    assert intents_v1[0].payload == intents_v2[0].payload


def test_classification_rule_payload_omits_separately_managed() -> None:
    desired = ClassificationRuleDesiredState(
        name="custom-rule",
        kind="Custom",
        classification_name="Contoso.Secret",
        minimum_percentage_match=80.0,
        rule_status="Enabled",
        data_patterns=(RegexClassificationPatternDesired(pattern="^a$"),),
        column_patterns=(RegexClassificationPatternDesired(pattern="^b$"),),
        description="desc",
    )
    payload = custom_classification_rule_put_payload(desired)
    props = payload["properties"]
    assert payload["kind"] == "Custom"
    assert "classificationAction" not in props
    assert "version" not in props
    assert "id" not in props
    assert props["description"] == "desc"


def test_scan_ruleset_payload_omits_custom_file_extensions() -> None:
    desired = ScanRuleSetDesiredState(
        name="custom-srs",
        kind="AzureStorage",
        scan_ruleset_type="Custom",
        file_extensions=("CSV",),
        excluded_system_classifications=(),
        included_custom_classification_rule_names=("custom-rule",),
    )
    payload = custom_azure_storage_scan_ruleset_put_payload(desired)
    scanning = payload["properties"]["scanningRule"]
    assert "customFileExtensions" not in scanning
    assert "version" not in payload
    assert "status" not in payload


def test_scan_payload_includes_top_level_parent() -> None:
    desired = ScanDesiredState(
        name="DailyScan",
        kind="AzureStorageMsi",
        data_source_name="ds-a",
        scan_ruleset_name="custom-srs",
        scan_ruleset_type="Custom",
        collection_reference_name="root",
    )
    payload = azure_storage_msi_scan_put_payload(desired)
    assert payload == {
        "dataSourceName": "ds-a",
        "kind": "AzureStorageMsi",
        "properties": {
            "collection": {"referenceName": "root"},
            "scanRulesetName": "custom-srs",
            "scanRulesetType": "Custom",
        },
    }


def test_composite_scan_identity_materializes_two_same_names() -> None:
    config = validate_config_text(_MULTI, format_hint="yaml")
    remote = build_remote_state_v2((), (), (), (), (), (), (), ())
    plan = build_governance_plan_v2(config, remote)
    intents = materialize_mutation_intents_v2(plan)
    scans = [item for item in intents if item.resource_type == "scan"]
    assert len(scans) == 2
    assert {(item.data_source_name, item.name) for item in scans} == {
        ("ds-a", "DailyScan"),
        ("ds-b", "DailyScan"),
    }
    assert scans[0].payload["dataSourceName"] == scans[0].data_source_name
    assert scans[1].payload["dataSourceName"] == scans[1].data_source_name


def test_scan_parent_tamper_fails_preflight() -> None:
    config = validate_config_text(_MULTI, format_hint="yaml")
    remote = build_remote_state_v2((), (), (), (), (), (), (), ())
    plan = build_governance_plan_v2(config, remote)
    tampered = []
    flipped = False
    for op in plan.operations:
        if op.resource_type == "scan" and not flipped:
            flipped = True
            tampered.append(
                type(op)(
                    sequence=op.sequence,
                    resource_type=op.resource_type,
                    name=op.name,
                    action=op.action,
                    data_source_name="missing-parent",
                )
            )
        else:
            tampered.append(op)
    object.__setattr__(plan, "operations", tuple(tampered))
    with pytest.raises(ApplyValidationError) as exc:
        materialize_mutation_intents_v2(plan)
    assert exc.value.code == "apply.payload_preflight_failed"
