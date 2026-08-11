"""Schema bounds for separately-managed classificationRule.version."""

from __future__ import annotations

from jsonschema import Draft202012Validator

from purview_governance.remote_state.classification_policy import INT32_MAX, INT32_MIN
from purview_governance.remote_state.schema import load_remote_state_v2_schema


def _minimal_remote_doc(*, version: object | None = 4, include_version: bool = True) -> dict:
    separately: dict = {"classificationAction": "Keep"}
    if include_version:
        separately["version"] = version
    return {
        "apiVersion": "purview-remote-state/v2",
        "dataSources": [],
        "uninterpretedDataSources": [],
        "classificationRules": [
            {
                "type": "classificationRule",
                "name": "RuleOne",
                "kind": "Custom",
                "properties": {
                    "classificationName": "CUSTOM.TEST",
                    "minimumPercentageMatch": 80.0,
                    "ruleStatus": "Enabled",
                    "dataPatterns": [],
                    "columnPatterns": [],
                },
                "separatelyManagedProperties": separately,
            }
        ],
        "uninterpretedClassificationRules": [],
        "scans": [],
        "uninterpretedScans": [],
        "scanRuleSets": [],
        "uninterpretedScanRuleSets": [],
        "materialStateIdentity": "sha256:" + ("a" * 64),
    }


def test_version_int32_bounds_in_schema() -> None:
    schema = load_remote_state_v2_schema()
    validator = Draft202012Validator(schema)
    assert list(validator.iter_errors(_minimal_remote_doc(version=INT32_MIN))) == []
    assert list(validator.iter_errors(_minimal_remote_doc(version=INT32_MAX))) == []
    assert list(validator.iter_errors(_minimal_remote_doc(include_version=False))) == []

    assert list(validator.iter_errors(_minimal_remote_doc(version=INT32_MIN - 1)))
    assert list(validator.iter_errors(_minimal_remote_doc(version=INT32_MAX + 1)))
    assert list(validator.iter_errors(_minimal_remote_doc(version=True)))
    assert list(validator.iter_errors(_minimal_remote_doc(version=None)))
