"""Versioned governance configuration contract (purview-governance-config)."""

from purview_governance.config.diagnostics import ConfigDiagnostic, ConfigValidationError
from purview_governance.config.models import (
    AuthenticationConfig,
    ClassificationRuleResourceConfig,
    DataSourceResourceConfig,
    GovernanceConfig,
    ScanResourceConfig,
    ScanRuleSetResourceConfig,
    TargetConfig,
    to_canonical_json,
)
from purview_governance.config.models_v3 import (
    BusinessDomainResourceConfig,
    GovernanceConfigV3,
    TargetConfigV3,
    to_canonical_json_v3,
)
from purview_governance.config.schema import load_v1_schema, load_v2_schema, load_v3_schema
from purview_governance.config.service import (
    validate_config_dict,
    validate_config_file,
    validate_config_text,
)
from purview_governance.config.service_v3 import (
    validate_config_v3_dict,
    validate_config_v3_file,
    validate_config_v3_text,
)

__all__ = [
    "AuthenticationConfig",
    "BusinessDomainResourceConfig",
    "ClassificationRuleResourceConfig",
    "ConfigDiagnostic",
    "ConfigValidationError",
    "DataSourceResourceConfig",
    "GovernanceConfig",
    "GovernanceConfigV3",
    "ScanResourceConfig",
    "ScanRuleSetResourceConfig",
    "TargetConfig",
    "TargetConfigV3",
    "load_v1_schema",
    "load_v2_schema",
    "load_v3_schema",
    "to_canonical_json",
    "to_canonical_json_v3",
    "validate_config_dict",
    "validate_config_file",
    "validate_config_text",
    "validate_config_v3_dict",
    "validate_config_v3_file",
    "validate_config_v3_text",
]
