"""Full-plan zero-write guards A–C for apply/v3."""

from __future__ import annotations

from purview_governance.apply import ExecutionMode, execute_governance_plan_v3
from purview_governance.apply.payloads_v3 import FAILURE_SEMANTICS_UNVERIFIED
from tests.apply.helpers_v3 import (
    DOMAIN_A,
    DOMAIN_B,
    DOMAIN_NEW,
    OWNER_ID,
    PRODUCT_A,
    PRODUCT_B,
    apply_server,
    base_config_header,
    build_plan_from_yaml,
    capture_remote_for_apply,
    make_tenant_bound_client,
)
from tests.contract.unified_catalog_server import fictional_business_domain_item


def _assert_zero_writes(result, server) -> None:
    assert result.status == "failed-before-write"
    assert result.writes_attempted == 0
    assert result.writes_performed == 0
    assert all(op.status == "not-run" for op in result.operations)
    assert not any(r.method in {"POST", "PUT"} for r in server.state.recordings)


def test_a_dp_create_safe_plus_bd_create_later_zero_writes() -> None:
    yaml_text = (
        base_config_header()
        + f"""
  - type: dataProduct
    id: {PRODUCT_A}
    properties:
      name: sales-product
      domain: {DOMAIN_A}
      type: Master
      description: Product description
      businessUse: Primary business use
      owners:
        - id: {OWNER_ID}
  - type: businessDomain
    id: {DOMAIN_NEW}
    properties:
      name: new-domain
      status: PUBLISHED
      type: DataDomain
"""
    )
    with apply_server() as server:
        client = make_tenant_bound_client(server.base_url)
        try:
            remote = capture_remote_for_apply(client, include_data_products=True)
            plan = build_plan_from_yaml(yaml_text, remote)
            assert plan.execution_eligibility == "ready"
            result = execute_governance_plan_v3(plan, remote, client, mode=ExecutionMode.APPLY)
        finally:
            client.close()
    assert result.failure is not None
    assert result.failure.code == FAILURE_SEMANTICS_UNVERIFIED
    _assert_zero_writes(result, server)


def test_b_term_create_safe_plus_child_to_root_later_zero_writes() -> None:
    yaml_text = (
        base_config_header()
        + f"""
  - type: dataProduct
    id: {PRODUCT_A}
    properties:
      name: sales-product
      domain: {DOMAIN_A}
      type: Master
      description: Product description
      businessUse: Primary business use
      owners:
        - id: {OWNER_ID}
  - type: businessDomain
    id: {DOMAIN_B}
    properties:
      name: child-domain
      status: DRAFT
      type: FunctionalUnit
"""
    )
    root = fictional_business_domain_item(domain_id=DOMAIN_A, name="root-domain")
    root["type"] = "DataDomain"
    child = fictional_business_domain_item(domain_id=DOMAIN_B, name="child-domain")
    child["parentId"] = DOMAIN_A
    child["type"] = "FunctionalUnit"
    child["status"] = "DRAFT"
    with apply_server(enumerate_items=[root, child]) as server:
        client = make_tenant_bound_client(server.base_url)
        try:
            remote = capture_remote_for_apply(client, include_data_products=True)
            plan = build_plan_from_yaml(yaml_text, remote)
            assert plan.execution_eligibility == "ready"
            result = execute_governance_plan_v3(plan, remote, client, mode=ExecutionMode.APPLY)
        finally:
            client.close()
    assert result.failure is not None
    assert result.failure.code == FAILURE_SEMANTICS_UNVERIFIED
    _assert_zero_writes(result, server)


def test_c_dp_create_depends_on_desired_bd_create_zero_writes() -> None:
    yaml_text = (
        base_config_header()
        + f"""
  - type: businessDomain
    id: {DOMAIN_NEW}
    properties:
      name: new-domain
      status: PUBLISHED
      type: DataDomain
  - type: dataProduct
    id: {PRODUCT_B}
    properties:
      name: dependent-product
      domain: {DOMAIN_NEW}
      type: Master
      description: Product description
      businessUse: Primary business use
      owners:
        - id: {OWNER_ID}
"""
    )
    with apply_server() as server:
        client = make_tenant_bound_client(server.base_url)
        try:
            remote = capture_remote_for_apply(client, include_data_products=True)
            plan = build_plan_from_yaml(yaml_text, remote)
            assert plan.execution_eligibility == "ready"
            result = execute_governance_plan_v3(plan, remote, client, mode=ExecutionMode.APPLY)
        finally:
            client.close()
    assert result.failure is not None
    assert result.failure.code == FAILURE_SEMANTICS_UNVERIFIED
    _assert_zero_writes(result, server)
