"""Versioned governance configuration contract (purview-governance-config)."""

from purview_governance.config.diagnostics import ConfigDiagnostic, ConfigValidationError
from purview_governance.config.models import (
    AuthenticationConfig,
    GovernanceConfig,
    TargetConfig,
    to_canonical_json,
)
from purview_governance.config.schema import load_v1_schema
from purview_governance.config.service import (
    validate_config_dict,
    validate_config_file,
    validate_config_text,
)

__all__ = [
    "AuthenticationConfig",
    "ConfigDiagnostic",
    "ConfigValidationError",
    "GovernanceConfig",
    "TargetConfig",
    "load_v1_schema",
    "to_canonical_json",
    "validate_config_dict",
    "validate_config_file",
    "validate_config_text",
]
