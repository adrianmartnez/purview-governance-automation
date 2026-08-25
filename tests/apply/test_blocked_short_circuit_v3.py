"""BLOCKED_PLAN_SHORT_CIRCUIT for apply/v3."""

from __future__ import annotations

from purview_governance.apply import ExecutionMode, execute_governance_plan_v3
from purview_governance.auth.provider import PurviewAuthorizationProvider
from purview_governance.config.service_v3 import validate_config_v3_text
from purview_governance.plan import build_governance_plan_v3
from purview_governance.remote_state.models_v3 import (
    NormalizedBusinessDomain,
    build_remote_state_v3,
)
from purview_governance.unified_catalog.client import PurviewUnifiedCatalogClient
from tests.apply.helpers_v3 import (
    DOMAIN_A,
    DOMAIN_B,
    DOMAIN_C,
    ENDPOINT,
    apply_server,
    target_context,
)
from tests.contract.unified_catalog_client_helpers import make_loopback_unified_catalog_client


class _ExplodingCredential:
    def get_token(self, *scopes: str, **kwargs: object) -> object:
        raise AssertionError("token acquisition must not run for blocked plans")


def _blocked_plan_and_remote():
    yaml_text = f"""
apiVersion: purview-governance-config/v3
target:
  surface: unifiedCatalog
  tenantId: {target_context().tenant_id}
authentication:
  strategy: defaultAzureCredential
resources:
  - type: businessDomain
    id: {DOMAIN_A}
    properties:
      name: root-domain
      status: PUBLISHED
      type: DataDomain
  - type: businessDomain
    id: {DOMAIN_B}
    properties:
      name: child-domain
      status: DRAFT
      type: FunctionalUnit
      parentId: {DOMAIN_A}
  - type: businessDomain
    id: {DOMAIN_C}
    properties:
      name: taken-name
      status: PUBLISHED
      type: DataDomain
"""
    remote = build_remote_state_v3(
        (
            NormalizedBusinessDomain(
                id="10000000-0000-4000-8000-000000000099",
                properties={
                    "name": "taken-name",
                    "status": "PUBLISHED",
                    "type": "DataDomain",
                },
            ),
        ),
        (),
        target_context(),
    )
    config = validate_config_v3_text(yaml_text, format_hint="yaml")
    plan = build_governance_plan_v3(config, remote)
    assert plan.execution_eligibility == "blocked"
    return plan, remote


def test_blocked_plan_short_circuit_zero_network_and_token() -> None:
    plan, remote = _blocked_plan_and_remote()
    provider = PurviewAuthorizationProvider(_ExplodingCredential())  # type: ignore[arg-type]
    with apply_server() as server:
        client = PurviewUnifiedCatalogClient._from_loopback_base_url(
            server.base_url,
            provider,
            logical_target_endpoint=ENDPOINT,
        )
        try:
            result = execute_governance_plan_v3(
                plan,
                remote,
                client,
                mode=ExecutionMode.APPLY,
            )
        finally:
            client.close()

    assert result.status == "blocked"
    assert result.failure is not None
    assert result.failure.code == "apply.plan_blocked"
    assert result.writes_attempted == 0
    assert result.writes_performed == 0
    assert all(op.status == "not-run" for op in result.operations)
    assert server.state.recordings == []


def test_blocked_plan_does_not_require_tenant_bound_provider() -> None:
    plan, remote = _blocked_plan_and_remote()
    with apply_server() as server:
        client = make_loopback_unified_catalog_client(server.base_url)
        try:
            result = execute_governance_plan_v3(plan, remote, client, mode=ExecutionMode.DRY_RUN)
        finally:
            client.close()

    assert result.status == "blocked"
    assert server.state.recordings == []
