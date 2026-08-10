"""Load packaged purview-governance-plan JSON Schemas."""

from __future__ import annotations

import json
from importlib import resources
from typing import Any


def load_plan_v1_schema() -> dict[str, Any]:
    """Load Draft 2020-12 schema for purview-governance-plan/v1 via importlib.resources."""
    package = resources.files("purview_governance.plan.schemas")
    schema_text = (package / "purview_governance_plan_v1.json").read_text(encoding="utf-8")
    schema = json.loads(schema_text)
    if not isinstance(schema, dict):
        msg = "governance-plan schema must be a JSON object"
        raise TypeError(msg)
    return schema


def load_plan_v2_schema() -> dict[str, Any]:
    """Load Draft 2020-12 schema for purview-governance-plan/v2 via importlib.resources."""
    package = resources.files("purview_governance.plan.schemas")
    schema_text = (package / "purview_governance_plan_v2.json").read_text(encoding="utf-8")
    schema = json.loads(schema_text)
    if not isinstance(schema, dict):
        msg = "governance-plan v2 schema must be a JSON object"
        raise TypeError(msg)
    return schema
