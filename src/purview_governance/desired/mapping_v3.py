"""Pure config -> desired-state mapping for governance config v3."""

from __future__ import annotations

from purview_governance.config.models_v3 import (
    BusinessDomainResourceConfig,
    DataProductResourceConfig,
    GovernanceConfigV3,
)
from purview_governance.desired.models_v3 import (
    BusinessDomainDesiredState,
    DataProductDesiredState,
    DataProductOwnerDesiredState,
    DesiredStateV3,
)


def desired_state_from_config_v3(config: GovernanceConfigV3) -> DesiredStateV3:
    """Map normalized governance config v3 to comparison desired state."""
    domains: list[BusinessDomainDesiredState] = []
    products: list[DataProductDesiredState] = []

    for resource in config.resources:
        if isinstance(resource, BusinessDomainResourceConfig):
            domains.append(
                BusinessDomainDesiredState(
                    id=resource.id,
                    name=resource.name,
                    description=resource.description,
                    parent_id=resource.parent_id,
                    status=resource.status,
                    domain_type=resource.domain_type,
                    is_restricted=resource.is_restricted,
                )
            )
        elif isinstance(resource, DataProductResourceConfig):
            products.append(
                DataProductDesiredState(
                    id=resource.id,
                    name=resource.name,
                    domain=resource.domain,
                    product_type=resource.product_type,
                    description=resource.description,
                    business_use=resource.business_use,
                    owners=tuple(
                        DataProductOwnerDesiredState(
                            id=owner.id,
                            description=owner.description,
                        )
                        for owner in resource.owners
                    ),
                    audience=resource.audience,
                    update_frequency=resource.update_frequency,
                    endorsed=resource.endorsed,
                )
            )

    return DesiredStateV3(
        business_domains=tuple(sorted(domains, key=lambda item: item.id)),
        data_products=tuple(sorted(products, key=lambda item: item.id)),
    )
