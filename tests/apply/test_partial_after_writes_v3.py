"""Partial status after successful writes for apply/v3."""

from __future__ import annotations

from purview_governance.apply import ExecutionMode, execute_governance_plan_v3
from tests.apply.helpers_v3 import (
    DOMAIN_A,
    DOMAIN_B,
    DOMAIN_C,
    apply_server,
    base_config_header,
    build_plan_from_yaml,
    capture_remote_for_apply,
    make_tenant_bound_client,
)
from tests.contract.unified_catalog_server import fictional_business_domain_item


def _two_child_domain_replace_yaml() -> str:
    return (
        base_config_header()
        + f"""
  - type: businessDomain
    id: {DOMAIN_B}
    properties:
      name: child-domain-renamed
      status: DRAFT
      type: FunctionalUnit
      parentId: {DOMAIN_A}
  - type: businessDomain
    id: {DOMAIN_C}
    properties:
      name: sibling-domain-renamed
      status: DRAFT
      type: FunctionalUnit
      parentId: {DOMAIN_A}
"""
    )


def _domain_fixtures() -> list[dict]:
    root = fictional_business_domain_item(domain_id=DOMAIN_A, name="root-domain")
    root["type"] = "DataDomain"
    child_b = fictional_business_domain_item(domain_id=DOMAIN_B, name="child-domain")
    child_b["parentId"] = DOMAIN_A
    child_b["type"] = "FunctionalUnit"
    child_b["status"] = "DRAFT"
    child_c = fictional_business_domain_item(domain_id=DOMAIN_C, name="sibling-domain")
    child_c["parentId"] = DOMAIN_A
    child_c["type"] = "FunctionalUnit"
    child_c["status"] = "DRAFT"
    return [root, child_b, child_c]


def _run_partial(kind: str) -> None:
    with apply_server(
        enumerate_items=_domain_fixtures(),
        second_preflight_fail_after_writes=1,
        second_preflight_fail_kind=kind,
    ) as server:
        client = make_tenant_bound_client(server.base_url)
        try:
            remote = capture_remote_for_apply(client)
            plan = build_plan_from_yaml(_two_child_domain_replace_yaml(), remote)
            result = execute_governance_plan_v3(plan, remote, client, mode=ExecutionMode.APPLY)
        finally:
            client.close()

    assert result.status == "partial"
    assert result.writes_performed == 1
    assert result.operations[0].status == "succeeded"
    assert result.operations[1].status == "not-run"


def test_partial_after_stale() -> None:
    _run_partial("stale")


def test_partial_after_auth_failure() -> None:
    with apply_server(
        enumerate_items=_domain_fixtures(),
        second_preflight_fail_after_writes=1,
        second_preflight_fail_kind="auth",
    ) as server:
        client = make_tenant_bound_client(server.base_url)
        try:
            remote = capture_remote_for_apply(client)
            plan = build_plan_from_yaml(_two_child_domain_replace_yaml(), remote)
            result = execute_governance_plan_v3(plan, remote, client, mode=ExecutionMode.APPLY)
        finally:
            client.close()
    assert result.status == "partial"
    assert result.failure is not None
    assert result.failure.code == "apply.pre_write_auth_failed_after_writes"


def test_partial_after_read_failure() -> None:
    with apply_server(
        enumerate_items=_domain_fixtures(),
        second_preflight_fail_after_writes=1,
        second_preflight_fail_kind="read",
    ) as server:
        client = make_tenant_bound_client(server.base_url)
        try:
            remote = capture_remote_for_apply(client)
            plan = build_plan_from_yaml(_two_child_domain_replace_yaml(), remote)
            result = execute_governance_plan_v3(plan, remote, client, mode=ExecutionMode.APPLY)
        finally:
            client.close()
    assert result.status == "partial"
    assert result.failure is not None
    assert result.failure.code == "apply.pre_write_read_failed_after_writes"


def test_partial_stale_failure_code() -> None:
    with apply_server(
        enumerate_items=_domain_fixtures(),
        second_preflight_fail_after_writes=1,
        second_preflight_fail_kind="stale",
    ) as server:
        client = make_tenant_bound_client(server.base_url)
        try:
            remote = capture_remote_for_apply(client)
            plan = build_plan_from_yaml(_two_child_domain_replace_yaml(), remote)
            result = execute_governance_plan_v3(plan, remote, client, mode=ExecutionMode.APPLY)
        finally:
            client.close()
    assert result.failure is not None
    assert result.failure.code == "apply.pre_write_stale_after_writes"
