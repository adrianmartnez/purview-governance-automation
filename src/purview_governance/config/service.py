"""Application service for governance configuration validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from purview_governance.config.loader import load_config_file, load_config_text
from purview_governance.config.models import GovernanceConfig
from purview_governance.config.normalize import normalize_document
from purview_governance.config.validate import validate_document


def validate_config_dict(document: dict[str, Any]) -> GovernanceConfig:
    """Validate and normalize an already-parsed configuration document."""
    validated = validate_document(document)
    return normalize_document(validated)


def validate_config_text(text: str, *, format_hint: str) -> GovernanceConfig:
    """Parse, validate, and normalize configuration text."""
    document = load_config_text(text, format_hint=format_hint)
    return validate_config_dict(document)


def validate_config_file(path: str | Path) -> GovernanceConfig:
    """Load, validate, and normalize a configuration file."""
    document = load_config_file(path)
    return validate_config_dict(document)
