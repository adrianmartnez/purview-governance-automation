"""Packaged JSON Schema loading for purview-governance-config."""

from __future__ import annotations

import json
from importlib import resources
from typing import Any

_SCHEMA_PACKAGE = "purview_governance.config.schemas"
_SCHEMA_V1_FILENAME = "purview_governance_config_v1.json"
_SCHEMA_V2_FILENAME = "purview_governance_config_v2.json"


def _load_schema(filename: str) -> dict[str, Any]:
    schema_text = resources.files(_SCHEMA_PACKAGE).joinpath(filename).read_text(encoding="utf-8")
    schema = json.loads(schema_text)
    if not isinstance(schema, dict):
        msg = "packaged governance config schema must be a JSON object"
        raise TypeError(msg)
    return schema


def load_v1_schema() -> dict[str, Any]:
    """Load the packaged Draft 2020-12 schema for contract v1."""
    return _load_schema(_SCHEMA_V1_FILENAME)


def load_v2_schema() -> dict[str, Any]:
    """Load the packaged Draft 2020-12 schema for contract v2."""
    return _load_schema(_SCHEMA_V2_FILENAME)
