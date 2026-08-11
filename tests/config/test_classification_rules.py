"""Config/desired tests for Custom Classification Rules (config/v2)."""

from __future__ import annotations

import math

import pytest

from purview_governance.config.diagnostics import ConfigValidationError
from purview_governance.config.service import validate_config_text
from purview_governance.desired.mapping import desired_state_from_config
from purview_governance.finite_double import FiniteDoubleError, canonicalize_finite_double


def _validate(text: str):
    return validate_config_text(text, format_hint="yaml")


def _base_yaml(*, properties: str) -> str:
    return f"""
apiVersion: purview-governance-config/v2
target:
  endpoint: https://example.purview.azure.com
authentication:
  strategy: defaultAzureCredential
resources:
  - type: classificationRule
    name: CustomerAccountRule
    kind: Custom
    properties:
{properties}
"""


def test_valid_classification_rule_with_patterns() -> None:
    config = _validate(
        _base_yaml(
            properties="""\
      classificationName: CUSTOM.CUSTOMER.ACCOUNT
      minimumPercentageMatch: 80
      ruleStatus: Enabled
      description: Detect customer account identifiers
      dataPatterns:
        - kind: Regex
          pattern: "^[0-9]{8}$"
        - kind: Regex
          pattern: "^[0-9]{8}$"
      columnPatterns:
        - kind: Regex
          pattern: "(?i)account"
"""
        )
    )
    rule = config.classification_rules[0]
    assert rule.classification_name == "CUSTOM.CUSTOMER.ACCOUNT"
    assert rule.minimum_percentage_match == 80.0
    assert isinstance(rule.minimum_percentage_match, float)
    assert rule.rule_status == "Enabled"
    assert rule.description == "Detect customer account identifiers"
    assert [p.pattern for p in rule.data_patterns] == ["^[0-9]{8}$", "^[0-9]{8}$"]
    assert [p.pattern for p in rule.column_patterns] == ["(?i)account"]

    desired = desired_state_from_config(config)
    assert desired.classification_rules[0].minimum_percentage_match == 80.0


def test_absent_patterns_map_to_empty_sequence() -> None:
    config = _validate(
        _base_yaml(
            properties="""\
      classificationName: CUSTOM.X
      minimumPercentageMatch: 60
      ruleStatus: Disabled
"""
        )
    )
    rule = config.classification_rules[0]
    assert rule.data_patterns == ()
    assert rule.column_patterns == ()


def test_empty_pattern_arrays() -> None:
    config = _validate(
        _base_yaml(
            properties="""\
      classificationName: CUSTOM.X
      minimumPercentageMatch: 60
      ruleStatus: Enabled
      dataPatterns: []
      columnPatterns: []
"""
        )
    )
    assert config.classification_rules[0].data_patterns == ()
    assert config.classification_rules[0].column_patterns == ()


def test_null_patterns_rejected() -> None:
    with pytest.raises(ConfigValidationError):
        _validate(
            _base_yaml(
                properties="""\
      classificationName: CUSTOM.X
      minimumPercentageMatch: 60
      ruleStatus: Enabled
      dataPatterns: null
"""
            )
        )


def test_null_description_rejected() -> None:
    with pytest.raises(ConfigValidationError):
        _validate(
            _base_yaml(
                properties="""\
      classificationName: CUSTOM.X
      minimumPercentageMatch: 60
      ruleStatus: Enabled
      description: null
"""
            )
        )


def test_empty_description_preserved() -> None:
    config = _validate(
        _base_yaml(
            properties="""\
      classificationName: CUSTOM.X
      minimumPercentageMatch: 60
      ruleStatus: Enabled
      description: ""
"""
        )
    )
    assert config.classification_rules[0].description == ""


def test_classification_name_empty_string_allowed() -> None:
    config = _validate(
        _base_yaml(
            properties="""\
      classificationName: ""
      minimumPercentageMatch: 60
      ruleStatus: Enabled
"""
        )
    )
    assert config.classification_rules[0].classification_name == ""


def test_classification_name_spaces_preserved() -> None:
    config = _validate(
        _base_yaml(
            properties="""\
      classificationName: " CUSTOM.X "
      minimumPercentageMatch: 60
      ruleStatus: Enabled
"""
        )
    )
    assert config.classification_rules[0].classification_name == " CUSTOM.X "


def test_regex_pattern_preserved_exactly() -> None:
    config = _validate(
        _base_yaml(
            properties="""\
      classificationName: CUSTOM.X
      minimumPercentageMatch: 60
      ruleStatus: Enabled
      dataPatterns:
        - kind: Regex
          pattern: "  ^[A-Z]\\\\d+$  "
"""
        )
    )
    assert config.classification_rules[0].data_patterns[0].pattern == r"  ^[A-Z]\d+$  "


def test_minimum_percentage_match_int_and_float_canonical() -> None:
    int_config = _validate(
        _base_yaml(
            properties="""\
      classificationName: CUSTOM.X
      minimumPercentageMatch: 80
      ruleStatus: Enabled
"""
        )
    )
    float_config = _validate(
        _base_yaml(
            properties="""\
      classificationName: CUSTOM.X
      minimumPercentageMatch: 80.0
      ruleStatus: Enabled
"""
        )
    )
    assert (
        int_config.classification_rules[0].minimum_percentage_match
        == float_config.classification_rules[0].minimum_percentage_match
        == 80.0
    )
    desired_int = desired_state_from_config(int_config).to_document(multi_resource=True)
    desired_float = desired_state_from_config(float_config).to_document(multi_resource=True)
    assert desired_int["classificationRules"] == desired_float["classificationRules"]


def test_minimum_percentage_match_rejects_bool_nan_inf() -> None:
    with pytest.raises(ConfigValidationError):
        _validate(
            _base_yaml(
                properties="""\
      classificationName: CUSTOM.X
      minimumPercentageMatch: true
      ruleStatus: Enabled
"""
            )
        )
    assert canonicalize_finite_double(80) == 80.0
    assert canonicalize_finite_double(-0.0) == 0.0
    with pytest.raises(FiniteDoubleError):
        canonicalize_finite_double(math.nan)
    with pytest.raises(FiniteDoubleError):
        canonicalize_finite_double(math.inf)


def test_duplicate_classification_rule_name() -> None:
    text = """
apiVersion: purview-governance-config/v2
target:
  endpoint: https://example.purview.azure.com
authentication:
  strategy: defaultAzureCredential
resources:
  - type: classificationRule
    name: SameRule
    kind: Custom
    properties:
      classificationName: A
      minimumPercentageMatch: 60
      ruleStatus: Enabled
  - type: classificationRule
    name: SameRule
    kind: Custom
    properties:
      classificationName: B
      minimumPercentageMatch: 60
      ruleStatus: Enabled
"""
    with pytest.raises(ConfigValidationError) as exc:
        _validate(text)
    assert any(d.code == "config.duplicate_classification_rule_name" for d in exc.value.diagnostics)


def test_system_kind_rejected() -> None:
    with pytest.raises(ConfigValidationError):
        _validate("""
apiVersion: purview-governance-config/v2
target:
  endpoint: https://example.purview.azure.com
authentication:
  strategy: defaultAzureCredential
resources:
  - type: classificationRule
    name: SystemLike
    kind: System
    properties:
      classificationName: A
      minimumPercentageMatch: 60
      ruleStatus: Enabled
""")
