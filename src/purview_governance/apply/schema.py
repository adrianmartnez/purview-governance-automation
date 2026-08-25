"""Load packaged purview-execution-result JSON Schemas."""

from __future__ import annotations

import json
from importlib import resources
from typing import Any


def load_execution_result_v1_schema() -> dict[str, Any]:
    """Load Draft 2020-12 schema for purview-execution-result/v1."""
    package = resources.files("purview_governance.apply.schemas")
    schema_text = (package / "purview_execution_result_v1.json").read_text(encoding="utf-8")
    schema = json.loads(schema_text)
    if not isinstance(schema, dict):
        msg = "execution-result schema must be a JSON object"
        raise TypeError(msg)
    return schema


def load_execution_result_v2_schema() -> dict[str, Any]:
    """Load Draft 2020-12 schema for purview-execution-result/v2."""
    package = resources.files("purview_governance.apply.schemas")
    schema_text = (package / "purview_execution_result_v2.json").read_text(encoding="utf-8")
    schema = json.loads(schema_text)
    if not isinstance(schema, dict):
        msg = "execution-result schema must be a JSON object"
        raise TypeError(msg)
    return schema


def load_execution_result_v3_schema() -> dict[str, Any]:
    """Load Draft 2020-12 schema for purview-execution-result/v3."""
    package = resources.files("purview_governance.apply.schemas")
    schema_text = (package / "purview_execution_result_v3.json").read_text(encoding="utf-8")
    schema = json.loads(schema_text)
    if not isinstance(schema, dict):
        msg = "execution-result schema must be a JSON object"
        raise TypeError(msg)
    return schema
