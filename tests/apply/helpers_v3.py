"""Shared helpers for apply/v3 tests."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from purview_governance.auth.tenant_bound import TenantBoundAuthorizationProvider
from purview_governance.config.models_v3 import CONFIG_API_VERSION_V3, UNIFIED_CATALOG_SURFACE
from purview_governance.config.service_v3 import validate_config_v3_text
from purview_governance.plan import build_governance_plan_v3
from purview_governance.plan.identity import compute_target_context_identity_v3
from purview_governance.plan.models_v3 import GovernancePlanV3
from purview_governance.remote_state.models_v3 import RemoteStateV3, RemoteTargetContextV3
from purview_governance.remote_state.service import capture_unified_catalog_remote_state_v3
from purview_governance.unified_catalog.client import PurviewUnifiedCatalogClient
from purview_governance.unified_catalog.constants import UNIFIED_CATALOG_PRODUCTION_ENDPOINT
from tests.auth.tenant_bound_fakes import OfflineClientSecretCredential
from tests.contract.auth import AUTH_SENTINEL
from tests.contract.unified_catalog_server import (
    UnifiedCatalogContractServer,
    fictional_business_domain_item,
    start_unified_catalog_contract_server,
)

TENANT_ID = "20000000-0000-4000-8000-000000000001"
OTHER_TENANT_ID = "30000000-0000-4000-8000-000000000002"
ENDPOINT = UNIFIED_CATALOG_PRODUCTION_ENDPOINT
DOMAIN_A = "10000000-0000-4000-8000-000000000001"
DOMAIN_B = "10000000-0000-4000-8000-000000000002"
DOMAIN_C = "10000000-0000-4000-8000-000000000003"
DOMAIN_CHILD = DOMAIN_B
DOMAIN_NEW = "10000000-0000-4000-8000-000000000099"
PRODUCT_A = "40000000-0000-4000-8000-000000000001"
PRODUCT_B = "40000000-0000-4000-8000-000000000002"
TERM_PARENT = "50000000-0000-4000-8000-000000000001"
TERM_CHILD = "50000000-0000-4000-8000-000000000002"
OWNER_ID = "30000000-0000-4000-8000-000000000001"


def target_context(*, tenant_id: str = TENANT_ID) -> RemoteTargetContextV3:
    identity = compute_target_context_identity_v3(
        surface="unifiedCatalog",
        tenant_id=tenant_id,
        endpoint=ENDPOINT,
    )
    return RemoteTargetContextV3(
        surface="unifiedCatalog",
        tenant_id=tenant_id,
        endpoint=ENDPOINT,
        identity=identity,
    )


def make_tenant_bound_client(
    base_url: str,
    *,
    tenant_id: str = TENANT_ID,
    endpoint: str = ENDPOINT,
) -> PurviewUnifiedCatalogClient:
    token = AUTH_SENTINEL.removeprefix("Bearer ").strip()
    credential = OfflineClientSecretCredential(token=token)
    provider = TenantBoundAuthorizationProvider(
        credential,
        tenant_id=tenant_id,
        endpoint=endpoint,
    )
    return PurviewUnifiedCatalogClient._from_loopback_base_url(
        base_url,
        provider,
        logical_target_endpoint=endpoint,
    )


def capture_remote_for_apply(
    client: PurviewUnifiedCatalogClient,
    *,
    include_data_products: bool = False,
    include_glossary_terms: bool = False,
) -> RemoteStateV3:
    return capture_unified_catalog_remote_state_v3(
        client,
        tenant_id=TENANT_ID,
        include_data_products=include_data_products,
        include_glossary_terms=include_glossary_terms,
    )


def build_plan_from_yaml(yaml_text: str, remote: RemoteStateV3) -> GovernancePlanV3:
    config = validate_config_v3_text(yaml_text, format_hint="yaml")
    return build_governance_plan_v3(config, remote)


def base_config_header(*, tenant_id: str = TENANT_ID, include_root_domain: bool = True) -> str:
    header = f"""
apiVersion: {CONFIG_API_VERSION_V3}
target:
  surface: {UNIFIED_CATALOG_SURFACE}
  tenantId: {tenant_id}
authentication:
  strategy: defaultAzureCredential
resources:
"""
    if include_root_domain:
        header += f"""
  - type: businessDomain
    id: {DOMAIN_A}
    properties:
      name: root-domain
      status: PUBLISHED
      type: DataDomain
"""
    return header


def _default_root_domain() -> dict:
    item = fictional_business_domain_item(domain_id=DOMAIN_A, name="root-domain")
    item["type"] = "DataDomain"
    return item


@contextmanager
def apply_server(**kwargs: object) -> Iterator[UnifiedCatalogContractServer]:
    defaults = {
        "enumerate_items": [_default_root_domain()],
    }
    defaults.update(kwargs)
    with start_unified_catalog_contract_server(**defaults) as server:  # type: ignore[arg-type]
        yield server
