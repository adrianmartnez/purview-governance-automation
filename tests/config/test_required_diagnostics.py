"""Required-field diagnostics must be structural and deterministic."""

from __future__ import annotations

import json

import pytest
from jsonschema.exceptions import ValidationError

from purview_governance.config import ConfigValidationError, validate_config_text
from purview_governance.config.validate import _collect_required_diagnostics


def test_multiple_missing_required_fields_have_deterministic_paths() -> None:
    text = json.dumps({"resources": []})
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config_text(text, format_hint="json")

    required = [
        d
        for d in exc_info.value.diagnostics
        if d.code == "config.unknown_field" and d.message.startswith("required field")
    ]
    paths = [d.path for d in required]
    assert paths == sorted(paths)
    assert "/apiVersion" in paths
    assert "/target" in paths
    assert "/authentication" in paths


def test_required_diagnostics_do_not_use_validation_error_message() -> None:
    error = ValidationError(
        message="THIS MESSAGE MUST NOT BE PARSED FOR FIELD NAMES",
        validator="required",
        validator_value=["apiVersion", "target", "authentication"],
        instance={"resources": []},
        path=[],
    )
    diagnostics = _collect_required_diagnostics(error)
    assert {d.path for d in diagnostics} == {"/apiVersion", "/target", "/authentication"}
    assert all("THIS MESSAGE" not in d.message for d in diagnostics)
