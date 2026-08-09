"""Packaged JSON Schema loading for purview-governance-config v1."""

from __future__ import annotations

import json
from importlib import resources
from typing import Any

_SCHEMA_PACKAGE = "purview_governance.config.schemas"
_SCHEMA_FILENAME = "purview_governance_config_v1.json"


def load_v1_schema() -> dict[str, Any]:
    """Load the packaged Draft 2020-12 schema for contract v1."""
    schema_text = (
        resources.files(_SCHEMA_PACKAGE).joinpath(_SCHEMA_FILENAME).read_text(encoding="utf-8")
    )
    schema = json.loads(schema_text)
    if not isinstance(schema, dict):
        msg = "packaged governance config schema must be a JSON object"
        raise TypeError(msg)
    return schema
