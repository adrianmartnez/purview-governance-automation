"""Pre-#27 v2 development-shape supersession (remote schema gap; plan loader)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from purview_governance.plan.errors import PlanSchemaError
from purview_governance.plan.identity import compute_plan_identity
from purview_governance.plan.loader import load_plan_text
from purview_governance.remote_state.canonical import compute_material_state_identity
from purview_governance.remote_state.schema import load_remote_state_v2_schema

_FIXTURE_DIR = Path(__file__).resolve().parent / "v2_pre27"
_REMOTE_STATE = _FIXTURE_DIR / "remote-state.json"
_PLAN = _FIXTURE_DIR / "plan.json"


def test_pre27_remote_state_identity_matches_old_shape() -> None:
    document = json.loads(_REMOTE_STATE.read_text(encoding="utf-8"))
    assert document["apiVersion"] == "purview-remote-state/v2"
    assert "classificationRules" not in document
    assert "uninterpretedClassificationRules" not in document

    old_identity_doc = {
        "apiVersion": document["apiVersion"],
        "dataSources": document["dataSources"],
        "uninterpretedDataSources": document["uninterpretedDataSources"],
        "scans": document["scans"],
        "uninterpretedScans": document["uninterpretedScans"],
        "scanRuleSets": document["scanRuleSets"],
        "uninterpretedScanRuleSets": document["uninterpretedScanRuleSets"],
    }
    assert compute_material_state_identity(old_identity_doc) == document["materialStateIdentity"]


def test_pre27_remote_state_fails_current_v2_schema_for_classification_keys() -> None:
    document = json.loads(_REMOTE_STATE.read_text(encoding="utf-8"))
    schema = load_remote_state_v2_schema()
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(document))
    assert errors

    missing: set[str] = set()
    for err in errors:
        if err.validator != "required":
            continue
        # Draft 2020-12 reports each missing required property separately.
        path = list(err.absolute_path)
        assert path == []
        validator_value = err.validator_value
        if isinstance(validator_value, list):
            for key in ("classificationRules", "uninterpretedClassificationRules"):
                if key in validator_value and (key in str(err.message) or key not in document):
                    missing.add(key)
        message = err.message
        if "classificationRules" in message:
            missing.add("classificationRules")
        if "uninterpretedClassificationRules" in message:
            missing.add("uninterpretedClassificationRules")

    assert "classificationRules" in missing
    assert "uninterpretedClassificationRules" in missing

    with pytest.raises(ValidationError):
        validator.validate(document)


def test_pre27_plan_loader_raises_development_shape_superseded() -> None:
    text = _PLAN.read_text(encoding="utf-8")
    document = json.loads(text)
    assert document["apiVersion"] == "purview-governance-plan/v2"
    assert "classificationRules" not in document["desiredState"]

    without = {key: value for key, value in document.items() if key != "planIdentity"}
    assert compute_plan_identity(without) == document["planIdentity"]

    with pytest.raises(PlanSchemaError) as exc:
        load_plan_text(text)
    assert exc.value.code == "plan.development_shape_superseded"
    assert "pre-#27" in exc.value.message
