"""Pure config -> desired-state mapping for governance config v3."""

from __future__ import annotations

from purview_governance.config.models_v3 import GovernanceConfigV3
from purview_governance.desired.models_v3 import BusinessDomainDesiredState, DesiredStateV3


def desired_state_from_config_v3(config: GovernanceConfigV3) -> DesiredStateV3:
    """Map normalized governance config v3 to comparison desired state."""
    domains = tuple(
        BusinessDomainDesiredState(
            id=resource.id,
            name=resource.name,
            description=resource.description,
            parent_id=resource.parent_id,
            status=resource.status,
            domain_type=resource.domain_type,
            is_restricted=resource.is_restricted,
        )
        for resource in config.business_domains
    )
    return DesiredStateV3(
        business_domains=tuple(sorted(domains, key=lambda item: item.id)),
    )
