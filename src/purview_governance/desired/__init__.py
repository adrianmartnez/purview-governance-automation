"""Desired-state models and mapping from governance config."""

from purview_governance.desired.mapping import desired_state_from_config
from purview_governance.desired.models import DataSourceDesiredState, DesiredState

__all__ = [
    "DataSourceDesiredState",
    "DesiredState",
    "desired_state_from_config",
]
