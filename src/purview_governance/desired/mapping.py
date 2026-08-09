"""Pure config -> desired-state mapping (no network / auth / mutation)."""

from __future__ import annotations

from purview_governance.config.models import GovernanceConfig
from purview_governance.desired.models import DataSourceDesiredState, DesiredState


def desired_state_from_config(config: GovernanceConfig) -> DesiredState:
    """Map normalized governance config to comparison desired state."""
    items = tuple(
        DataSourceDesiredState(
            name=resource.name,
            kind="AzureStorage",
            endpoint=resource.endpoint,
            collection_reference_name=resource.collection_reference_name,
        )
        for resource in config.resources
    )
    # Config normalize already sorts by name; keep explicit for purity.
    return DesiredState(data_sources=tuple(sorted(items, key=lambda item: item.name)))
