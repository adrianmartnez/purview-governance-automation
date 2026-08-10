"""Load the packaged purview-remote-state JSON Schemas."""

from __future__ import annotations

import json
from importlib import resources
from typing import Any


def load_remote_state_v1_schema() -> dict[str, Any]:
    """Load Draft 2020-12 schema for purview-remote-state/v1 via importlib.resources."""
    package = resources.files("purview_governance.remote_state.schemas")
    schema_text = (package / "purview_remote_state_v1.json").read_text(encoding="utf-8")
    schema = json.loads(schema_text)
    if not isinstance(schema, dict):
        msg = "remote-state schema must be a JSON object"
        raise TypeError(msg)
    return schema


def load_remote_state_v2_schema() -> dict[str, Any]:
    """Load Draft 2020-12 schema for purview-remote-state/v2 via importlib.resources."""
    package = resources.files("purview_governance.remote_state.schemas")
    schema_text = (package / "purview_remote_state_v2.json").read_text(encoding="utf-8")
    schema = json.loads(schema_text)
    if not isinstance(schema, dict):
        msg = "remote-state schema must be a JSON object"
        raise TypeError(msg)
    return schema
