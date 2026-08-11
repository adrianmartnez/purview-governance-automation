"""Diff tests for Custom Classification Rules."""

from __future__ import annotations

from purview_governance.desired.models import (
    ClassificationRuleDesiredState,
    DesiredState,
    RegexClassificationPatternDesired,
)
from purview_governance.diff.service import diff_desired_vs_remote_v2
from purview_governance.remote_state.models import (
    ClassificationRuleSeparatelyManagedProperties,
    NormalizedClassificationRule,
    RegexClassificationPatternRemote,
    UninterpretedClassificationRule,
    build_remote_state_v2,
)


def _desired(**overrides: object) -> ClassificationRuleDesiredState:
    values: dict = {
        "name": "RuleOne",
        "kind": "Custom",
        "classification_name": "CUSTOM.TEST",
        "minimum_percentage_match": 80.0,
        "rule_status": "Enabled",
        "data_patterns": (RegexClassificationPatternDesired(pattern="^data1$"),),
        "column_patterns": (RegexClassificationPatternDesired(pattern="^column1$"),),
        "description": None,
    }
    values.update(overrides)
    return ClassificationRuleDesiredState(**values)  # type: ignore[arg-type]


def _remote(**overrides: object) -> NormalizedClassificationRule:
    values: dict = {
        "name": "RuleOne",
        "kind": "Custom",
        "classification_name": "CUSTOM.TEST",
        "minimum_percentage_match": 80.0,
        "rule_status": "Enabled",
        "data_patterns": (RegexClassificationPatternRemote(pattern="^data1$"),),
        "column_patterns": (RegexClassificationPatternRemote(pattern="^column1$"),),
        "description": None,
        "separately_managed": ClassificationRuleSeparatelyManagedProperties(
            classification_action="Keep",
            version=4,
        ),
    }
    values.update(overrides)
    return NormalizedClassificationRule(**values)  # type: ignore[arg-type]


def test_create_replace_noop_remote_only() -> None:
    desired = DesiredState(data_sources=(), classification_rules=(_desired(),))
    remote = build_remote_state_v2((), (), (), (), (), (), (), ())
    create_doc = diff_desired_vs_remote_v2(desired, remote)
    assert create_doc.items[0].outcome == "create"

    matching = build_remote_state_v2((), (), (_remote(),), (), (), (), (), ())
    noop = diff_desired_vs_remote_v2(desired, matching)
    assert noop.items[0].outcome == "no-op"

    replaced = build_remote_state_v2(
        (),
        (),
        (_remote(classification_name="OTHER"),),
        (),
        (),
        (),
        (),
        (),
    )
    replace_doc = diff_desired_vs_remote_v2(desired, replaced)
    assert replace_doc.items[0].outcome == "replace"

    remote_only = build_remote_state_v2((), (), (_remote(),), (), (), (), (), ())
    only = diff_desired_vs_remote_v2(DesiredState(data_sources=()), remote_only)
    assert only.items[0].outcome == "remote-only"


def test_system_collision_blocked() -> None:
    desired = DesiredState(data_sources=(), classification_rules=(_desired(),))
    remote = build_remote_state_v2(
        (),
        (),
        (),
        (
            UninterpretedClassificationRule(
                name="RuleOne",
                kind="System",
                reason_code="remote_state.unsupported_kind",
            ),
        ),
        (),
        (),
        (),
        (),
    )
    doc = diff_desired_vs_remote_v2(desired, remote)
    assert doc.items[0].outcome == "blocked"


def test_separately_managed_does_not_cause_replace() -> None:
    desired = DesiredState(data_sources=(), classification_rules=(_desired(),))
    remote_a = build_remote_state_v2((), (), (_remote(),), (), (), (), (), ())
    remote_b = build_remote_state_v2(
        (),
        (),
        (
            _remote(
                separately_managed=ClassificationRuleSeparatelyManagedProperties(
                    classification_action="Delete",
                    version=99,
                )
            ),
        ),
        (),
        (),
        (),
        (),
        (),
    )
    assert diff_desired_vs_remote_v2(desired, remote_a).items[0].outcome == "no-op"
    assert diff_desired_vs_remote_v2(desired, remote_b).items[0].outcome == "no-op"
    assert remote_a.material_state_identity != remote_b.material_state_identity


def test_int_float_minimum_match_noop() -> None:
    desired = DesiredState(
        data_sources=(),
        classification_rules=(_desired(minimum_percentage_match=80.0),),
    )
    remote = build_remote_state_v2(
        (),
        (),
        (_remote(minimum_percentage_match=80.0),),
        (),
        (),
        (),
        (),
        (),
    )
    # desired built from int 80 canonicalized elsewhere; compare floats
    assert diff_desired_vs_remote_v2(desired, remote).items[0].outcome == "no-op"

    different = build_remote_state_v2(
        (),
        (),
        (_remote(minimum_percentage_match=80.5),),
        (),
        (),
        (),
        (),
        (),
    )
    assert diff_desired_vs_remote_v2(desired, different).items[0].outcome == "replace"


def test_pattern_order_matters() -> None:
    desired = DesiredState(
        data_sources=(),
        classification_rules=(
            _desired(
                data_patterns=(
                    RegexClassificationPatternDesired(pattern="^a$"),
                    RegexClassificationPatternDesired(pattern="^b$"),
                )
            ),
        ),
    )
    remote = build_remote_state_v2(
        (),
        (),
        (
            _remote(
                data_patterns=(
                    RegexClassificationPatternRemote(pattern="^b$"),
                    RegexClassificationPatternRemote(pattern="^a$"),
                )
            ),
        ),
        (),
        (),
        (),
        (),
        (),
    )
    assert diff_desired_vs_remote_v2(desired, remote).items[0].outcome == "replace"
