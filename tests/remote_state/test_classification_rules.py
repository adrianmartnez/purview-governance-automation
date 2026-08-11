"""Remote normalize / identity tests for Custom Classification Rules."""

from __future__ import annotations

import pytest

from purview_governance.remote_state.canonical import compute_material_state_identity
from purview_governance.remote_state.classification_normalize import (
    normalize_custom_classification_rule_get,
)
from purview_governance.remote_state.errors import RemoteStateError
from purview_governance.remote_state.models import (
    ClassificationRuleSeparatelyManagedProperties,
    NormalizedClassificationRule,
    RegexClassificationPatternRemote,
    build_remote_state_v2,
)


def _custom_body(**property_overrides: object) -> dict:
    properties: dict = {
        "classificationName": "CUSTOM.TEST",
        "minimumPercentageMatch": 80,
        "ruleStatus": "Enabled",
        "dataPatterns": [{"kind": "Regex", "pattern": "^data1$"}],
        "columnPatterns": [{"kind": "Regex", "pattern": "^column1$"}],
        "classificationAction": "Keep",
        "version": 4,
        "createdAt": "2019-12-09T06:43:30.8478469Z",
        "lastModifiedAt": "2019-12-09T07:04:53.2807344Z",
    }
    properties.update(property_overrides)
    return {
        "id": "/classificationRules/RuleOne",
        "name": "RuleOne",
        "kind": "Custom",
        "properties": properties,
    }


def test_normalize_custom_preserves_patterns_and_float() -> None:
    rule = normalize_custom_classification_rule_get(_custom_body(), requested_name="RuleOne")
    assert rule.minimum_percentage_match == 80.0
    assert isinstance(rule.minimum_percentage_match, float)
    assert [p.pattern for p in rule.data_patterns] == ["^data1$"]
    assert rule.separately_managed.classification_action == "Keep"
    assert rule.separately_managed.version == 4


def test_int_and_float_minimum_match_same_identity() -> None:
    a = normalize_custom_classification_rule_get(
        _custom_body(minimumPercentageMatch=80),
        requested_name="RuleOne",
    )
    b = normalize_custom_classification_rule_get(
        _custom_body(minimumPercentageMatch=80.0),
        requested_name="RuleOne",
    )
    state_a = build_remote_state_v2((), (), (a,), (), (), (), (), ())
    state_b = build_remote_state_v2((), (), (b,), (), (), (), (), ())
    assert state_a.material_state_identity == state_b.material_state_identity


def test_action_and_version_affect_identity_not_material_equality_alone() -> None:
    base = normalize_custom_classification_rule_get(_custom_body(), requested_name="RuleOne")
    other_action = normalize_custom_classification_rule_get(
        _custom_body(classificationAction="Delete"),
        requested_name="RuleOne",
    )
    other_version = normalize_custom_classification_rule_get(
        _custom_body(version=5),
        requested_name="RuleOne",
    )
    assert (
        build_remote_state_v2((), (), (base,), (), (), (), (), ()).material_state_identity
        != build_remote_state_v2(
            (), (), (other_action,), (), (), (), (), ()
        ).material_state_identity
    )
    assert (
        build_remote_state_v2((), (), (base,), (), (), (), (), ()).material_state_identity
        != build_remote_state_v2(
            (), (), (other_version,), (), (), (), (), ()
        ).material_state_identity
    )


def test_null_patterns_fail_closed() -> None:
    with pytest.raises(RemoteStateError) as exc:
        normalize_custom_classification_rule_get(
            _custom_body(dataPatterns=None),
            requested_name="RuleOne",
        )
    assert exc.value.code == "remote_state.invalid_shape"


def test_null_description_fail_closed() -> None:
    with pytest.raises(RemoteStateError) as exc:
        normalize_custom_classification_rule_get(
            _custom_body(description=None),
            requested_name="RuleOne",
        )
    assert exc.value.code == "remote_state.invalid_shape"


def test_absent_patterns_are_empty() -> None:
    body = _custom_body()
    del body["properties"]["dataPatterns"]
    del body["properties"]["columnPatterns"]
    rule = normalize_custom_classification_rule_get(body, requested_name="RuleOne")
    assert rule.data_patterns == ()
    assert rule.column_patterns == ()


def test_invalid_action_and_version() -> None:
    with pytest.raises(RemoteStateError):
        normalize_custom_classification_rule_get(
            _custom_body(classificationAction="Nope"),
            requested_name="RuleOne",
        )
    with pytest.raises(RemoteStateError):
        normalize_custom_classification_rule_get(
            _custom_body(version=True),
            requested_name="RuleOne",
        )
    with pytest.raises(RemoteStateError):
        normalize_custom_classification_rule_get(
            _custom_body(version=2**40),
            requested_name="RuleOne",
        )


def test_absent_action_version_ok() -> None:
    body = _custom_body()
    del body["properties"]["classificationAction"]
    del body["properties"]["version"]
    rule = normalize_custom_classification_rule_get(body, requested_name="RuleOne")
    assert rule.separately_managed.to_document() == {}


def test_precompute_identity_document_excludes_identity_field() -> None:
    rule = NormalizedClassificationRule(
        name="RuleOne",
        kind="Custom",
        classification_name="CUSTOM.TEST",
        minimum_percentage_match=80.0,
        rule_status="Enabled",
        data_patterns=(RegexClassificationPatternRemote(pattern="^x$"),),
        separately_managed=ClassificationRuleSeparatelyManagedProperties(
            classification_action="Keep",
            version=1,
        ),
    )
    state = build_remote_state_v2((), (), (rule,), (), (), (), (), ())
    identity_doc = state.identity_document()
    assert "materialStateIdentity" not in identity_doc
    assert compute_material_state_identity(identity_doc) == state.material_state_identity
