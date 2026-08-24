"""Application service for governance configuration validation (v3)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from purview_governance.config.loader import load_config_file, load_config_text
from purview_governance.config.models_v3 import GovernanceConfigV3
from purview_governance.config.normalize_v3 import normalize_document_v3
from purview_governance.config.validate_v3 import validate_document_v3


def validate_config_v3_dict(document: dict[str, Any]) -> GovernanceConfigV3:
    """Validate and normalize an already-parsed v3 configuration document."""
    validated = validate_document_v3(document)
    return normalize_document_v3(validated)


def validate_config_v3_text(text: str, *, format_hint: str) -> GovernanceConfigV3:
    """Parse, validate, and normalize v3 configuration text."""
    document = load_config_text(text, format_hint=format_hint)
    return validate_config_v3_dict(document)


def validate_config_v3_file(path: str | Path) -> GovernanceConfigV3:
    """Load, validate, and normalize a v3 configuration file."""
    document = load_config_file(path)
    return validate_config_v3_dict(document)
