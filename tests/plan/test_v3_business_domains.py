"""Tests for governance plan v3 Business Domains."""

from __future__ import annotations

import pytest

from purview_governance.config.models_v3 import (
    CONFIG_API_VERSION_V3,
    MAX_BUSINESS_DOMAINS,
    UNIFIED_CATALOG_SURFACE,
)
from purview_governance.config.service_v3 import validate_config_v3_text
from purview_governance.plan import build_governance_plan_v3, load_plan_v3_text
from purview_governance.plan.errors import PlanBuildError
from purview_governance.plan.identity import compute_target_context_identity_v3
from purview_governance.remote_state.models_v3 import (
    NormalizedBusinessDomain,
    RemoteTargetContextV3,
    build_remote_state_v3,
)

TENANT_ID = "20000000-0000-4000-8000-000000000001"
ENDPOINT = "https://catalog.purview.azure.com"
DOMAIN_A = "10000000-0000-4000-8000-000000000001"
DOMAIN_B = "10000000-0000-4000-8000-000000000002"
DOMAIN_C = "10000000-0000-4000-8000-000000000003"


def _target_context() -> RemoteTargetContextV3:
    identity = compute_target_context_identity_v3(
        surface="unifiedCatalog",
        tenant_id=TENANT_ID,
        endpoint=ENDPOINT,
    )
    return RemoteTargetContextV3(
        surface="unifiedCatalog",
        tenant_id=TENANT_ID,
        endpoint=ENDPOINT,
        identity=identity,
    )


def _config_yaml(*extra_resources: str) -> str:
    base = f"""
apiVersion: {CONFIG_API_VERSION_V3}
target:
  surface: {UNIFIED_CATALOG_SURFACE}
  tenantId: {TENANT_ID}
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
"""
    if extra_resources:
        base = base.rstrip() + "\n" + "\n".join(extra_resources) + "\n"
    return base


def _empty_remote() -> build_remote_state_v3:
    return build_remote_state_v3((), (), _target_context())


def test_build_plan_v3_create_ordering_and_round_trip() -> None:
    config = validate_config_v3_text(_config_yaml(), format_hint="yaml")
    remote = _empty_remote()
    plan = build_governance_plan_v3(config, remote)

    assert plan.execution_eligibility == "ready"
    assert plan.summary.create == 2
    assert plan.summary.operations == 2
    assert plan.operations[0].id == DOMAIN_A
    assert plan.operations[0].action == "create"
    assert plan.operations[1].id == DOMAIN_B
    assert plan.operations[1].action == "create"

    loaded = load_plan_v3_text(plan.to_canonical_json())
    assert loaded.plan_identity == plan.plan_identity
    assert loaded.to_canonical_json() == plan.to_canonical_json()


def test_build_plan_v3_blocked_eligibility() -> None:
    config = validate_config_v3_text(
        _config_yaml(
            f"""
  - type: businessDomain
    id: {DOMAIN_C}
    properties:
      name: taken-name
      status: PUBLISHED
      type: DataDomain
"""
        ),
        format_hint="yaml",
    )
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
        _target_context(),
    )
    plan = build_governance_plan_v3(config, remote)
    assert plan.execution_eligibility == "blocked"
    assert plan.summary.blocked == 1
    assert plan.summary.operations == 2


def test_build_plan_v3_hierarchy_depth_exceeded() -> None:
    ids = [f"20000000-0000-4000-8000-{index:012x}" for index in range(1, 7)]
    remote_domains = tuple(
        NormalizedBusinessDomain(
            id=domain_id,
            properties={
                "name": f"remote-{index}",
                "status": "PUBLISHED",
                "type": "DataDomain",
                **({"parentId": ids[index - 2]} if index > 1 else {}),
            },
        )
        for index, domain_id in enumerate(ids, start=1)
    )
    remote = build_remote_state_v3(remote_domains, (), _target_context())
    config = validate_config_v3_text(
        f"""
apiVersion: {CONFIG_API_VERSION_V3}
target:
  surface: {UNIFIED_CATALOG_SURFACE}
  tenantId: {TENANT_ID}
authentication:
  strategy: defaultAzureCredential
resources: []
""",
        format_hint="yaml",
    )
    with pytest.raises(PlanBuildError, match="hierarchy_depth_exceeded"):
        build_governance_plan_v3(config, remote)


def test_build_plan_v3_unresolved_parent_blocks() -> None:
    missing_parent = "10000000-0000-4000-8000-0000000000ff"
    config = validate_config_v3_text(
        _config_yaml(
            f"""
  - type: businessDomain
    id: {DOMAIN_C}
    properties:
      name: orphan-child
      status: PUBLISHED
      type: DataDomain
      parentId: {missing_parent}
"""
        ),
        format_hint="yaml",
    )
    remote = _empty_remote()
    with pytest.raises(PlanBuildError, match="hierarchy_ambiguous"):
        build_governance_plan_v3(config, remote)


def test_build_plan_v3_count_limit() -> None:
    remote_domains = tuple(
        NormalizedBusinessDomain(
            id=f"{index:08x}-0000-4000-8000-000000000001",
            properties={
                "name": f"domain-{index}",
                "status": "PUBLISHED",
                "type": "DataDomain",
            },
        )
        for index in range(MAX_BUSINESS_DOMAINS)
    )
    remote = build_remote_state_v3(remote_domains, (), _target_context())
    config = validate_config_v3_text(
        f"""
apiVersion: {CONFIG_API_VERSION_V3}
target:
  surface: {UNIFIED_CATALOG_SURFACE}
  tenantId: {TENANT_ID}
authentication:
  strategy: defaultAzureCredential
resources:
  - type: businessDomain
    id: {DOMAIN_C}
    properties:
      name: overflow-domain
      status: PUBLISHED
      type: DataDomain
""",
        format_hint="yaml",
    )
    with pytest.raises(PlanBuildError, match="business_domain_count_exceeded"):
        build_governance_plan_v3(config, remote)
