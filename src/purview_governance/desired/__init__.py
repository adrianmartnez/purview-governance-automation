"""Desired-state models and mapping from governance config."""

from purview_governance.desired.mapping import desired_state_from_config
from purview_governance.desired.models import (
    ClassificationRuleDesiredState,
    DataSourceDesiredState,
    DesiredState,
    RegexClassificationPatternDesired,
    ScanDesiredState,
    ScanRuleSetDesiredState,
)

__all__ = [
    "ClassificationRuleDesiredState",
    "DataSourceDesiredState",
    "DesiredState",
    "RegexClassificationPatternDesired",
    "ScanDesiredState",
    "ScanRuleSetDesiredState",
    "desired_state_from_config",
]
