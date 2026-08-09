"""YAML mapping keys must be strings; complex keys fail closed."""

from __future__ import annotations

import pytest

from purview_governance.config import ConfigValidationError, validate_config_text


def test_yaml_sequence_key_rejected() -> None:
    text = """
? [a, b]
: value
apiVersion: purview-governance-config/v1
"""
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config_text(text, format_hint="yaml")
    assert exc_info.value.diagnostics[0].code == "config.invalid_syntax"
    assert "mapping keys must be strings" in exc_info.value.diagnostics[0].message


def test_yaml_mapping_key_rejected() -> None:
    text = """
? {a: 1}
: value
apiVersion: purview-governance-config/v1
"""
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config_text(text, format_hint="yaml")
    assert exc_info.value.diagnostics[0].code == "config.invalid_syntax"
    assert "mapping keys must be strings" in exc_info.value.diagnostics[0].message


def test_yaml_boolean_key_rejected() -> None:
    text = """
true: nope
apiVersion: purview-governance-config/v1
target:
  endpoint: https://contoso-fictional.purview.azure.com
authentication:
  strategy: defaultAzureCredential
resources: []
"""
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config_text(text, format_hint="yaml")
    assert exc_info.value.diagnostics[0].code == "config.invalid_syntax"
    assert "mapping keys must be strings" in exc_info.value.diagnostics[0].message


def test_yaml_quoted_true_key_is_unknown_string_field() -> None:
    text = """
apiVersion: purview-governance-config/v1
"true": nope
target:
  endpoint: https://contoso-fictional.purview.azure.com
authentication:
  strategy: defaultAzureCredential
resources: []
"""
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config_text(text, format_hint="yaml")
    diag = next(d for d in exc_info.value.diagnostics if d.path.endswith("true"))
    assert diag.code == "config.unknown_field"
