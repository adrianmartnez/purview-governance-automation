"""Tenant-bound APPLY seam and read-only client compatibility."""

from __future__ import annotations

import pytest
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from tests.apply.helpers_v3 import (
    DOMAIN_A,
    ENDPOINT,
    OTHER_TENANT_ID,
    TENANT_ID,
    apply_server,
    base_config_header,
    build_plan_from_yaml,
    capture_remote_for_apply,
    make_tenant_bound_client,
)
from tests.contract.unified_catalog_client_helpers import make_loopback_unified_catalog_client

from purview_governance.apply import ExecutionMode, execute_governance_plan_v3
from purview_governance.auth.tenant_bound import (
    TenantBindingUnsupportedError,
    TenantBoundAuthorizationProvider,
)
from purview_governance.remote_state.service import capture_unified_catalog_remote_state_v3


def test_read_only_client_auth_compat_for_capture() -> None:
    with apply_server() as server:
        client = make_loopback_unified_catalog_client(server.base_url)
        try:
            state = capture_unified_catalog_remote_state_v3(client, tenant_id=TENANT_ID)
        finally:
            client.close()
    assert len(state.business_domains) == 1


def test_apply_tenant_bound_required() -> None:
    yaml_text = (
        base_config_header()
        + f"""
  - type: glossaryTerm
    id: 50000000-0000-4000-8000-000000000001
    properties:
      name: parent-term
      domain: {DOMAIN_A}
      description: Parent term
      owners:
        - id: 30000000-0000-4000-8000-000000000001
"""
    )
    with apply_server() as server:
        client = make_loopback_unified_catalog_client(server.base_url)
        try:
            remote = capture_remote_for_apply(client, include_glossary_terms=True)
            plan = build_plan_from_yaml(yaml_text, remote)
            result = execute_governance_plan_v3(plan, remote, client, mode=ExecutionMode.DRY_RUN)
        finally:
            client.close()
    assert result.status == "failed-before-write"
    assert result.failure is not None
    assert result.failure.code == "apply.tenant_binding_unsupported"


def test_caller_tenant_spoof_impossible_wrong_target() -> None:
    yaml_text = (
        base_config_header(tenant_id=TENANT_ID)
        + f"""
  - type: glossaryTerm
    id: 50000000-0000-4000-8000-000000000001
    properties:
      name: parent-term
      domain: {DOMAIN_A}
      description: Parent term
      owners:
        - id: 30000000-0000-4000-8000-000000000001
"""
    )
    with apply_server() as server:
        planner = make_tenant_bound_client(server.base_url, tenant_id=TENANT_ID)
        try:
            remote = capture_remote_for_apply(planner, include_glossary_terms=True)
            plan = build_plan_from_yaml(yaml_text, remote)
        finally:
            planner.close()
        executor = make_tenant_bound_client(server.base_url, tenant_id=OTHER_TENANT_ID)
        try:
            result = execute_governance_plan_v3(plan, remote, executor, mode=ExecutionMode.DRY_RUN)
        finally:
            executor.close()
    assert result.status == "wrong-target"
    assert result.failure is not None
    assert result.failure.code == "apply.wrong_target"


def test_managed_identity_rejected_for_apply() -> None:
    with pytest.raises(TenantBindingUnsupportedError):
        TenantBoundAuthorizationProvider(
            ManagedIdentityCredential(),  # type: ignore[arg-type]
            tenant_id=TENANT_ID,
            endpoint=ENDPOINT,
        )


def test_default_azure_credential_rejected_for_apply() -> None:
    with pytest.raises(TenantBindingUnsupportedError):
        TenantBoundAuthorizationProvider(
            DefaultAzureCredential(),  # type: ignore[arg-type]
            tenant_id=TENANT_ID,
            endpoint=ENDPOINT,
        )


def test_client_secret_credential_allowed() -> None:
    from azure.identity import ClientSecretCredential

    provider = TenantBoundAuthorizationProvider(
        ClientSecretCredential("tenant", "client", "secret"),  # type: ignore[arg-type]
        tenant_id=TENANT_ID,
        endpoint=ENDPOINT,
    )
    assert provider.execution_tenant_id == TENANT_ID
