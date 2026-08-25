"""Unified Catalog apply/v3 contract harness tests."""

from __future__ import annotations

import pytest

from purview_governance.apply import ExecutionMode, execute_governance_plan_v3
from purview_governance.unified_catalog.constants import BUSINESS_DOMAINS_PATH
from tests.apply.helpers_v3 import (
    DOMAIN_A,
    DOMAIN_B,
    DOMAIN_NEW,
    OWNER_ID,
    TERM_PARENT,
    _default_root_domain,
    apply_server,
    base_config_header,
    build_plan_from_yaml,
    capture_remote_for_apply,
    make_tenant_bound_client,
)
from tests.contract.unified_catalog_server import fictional_business_domain_item


def test_bd_create_zero_calls() -> None:
    yaml_text = (
        base_config_header()
        + f"""
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
            remote = capture_remote_for_apply(client)
            plan = build_plan_from_yaml(yaml_text, remote)
            result = execute_governance_plan_v3(plan, remote, client, mode=ExecutionMode.APPLY)
        finally:
            client.close()
    post_bd = [
        r for r in server.state.recordings if r.method == "POST" and r.path == BUSINESS_DOMAINS_PATH
    ]
    assert post_bd == []
    assert result.status == "failed-before-write"


@pytest.mark.api_contract
def test_contract_put_business_domain_round_trip() -> None:
    yaml_text = (
        base_config_header()
        + f"""
  - type: businessDomain
    id: {DOMAIN_B}
    properties:
      name: child-domain-renamed
      status: DRAFT
      type: FunctionalUnit
      parentId: {DOMAIN_A}
"""
    )
    root = _default_root_domain()
    child = fictional_business_domain_item(domain_id=DOMAIN_B, name="child-domain")
    child["parentId"] = DOMAIN_A
    child["type"] = "FunctionalUnit"
    child["status"] = "DRAFT"
    with apply_server(enumerate_items=[root, child]) as server:
        client = make_tenant_bound_client(server.base_url)
        try:
            remote = capture_remote_for_apply(client)
            plan = build_plan_from_yaml(yaml_text, remote)
            result = execute_governance_plan_v3(plan, remote, client, mode=ExecutionMode.APPLY)
        finally:
            client.close()
    assert result.status == "applied"
    assert server.state.business_domains_by_id[DOMAIN_B]["name"] == "child-domain-renamed"


@pytest.mark.api_contract
def test_contract_post_glossary_term_create() -> None:
    yaml_text = (
        base_config_header()
        + f"""
  - type: glossaryTerm
    id: {TERM_PARENT}
    properties:
      name: parent-term
      domain: {DOMAIN_A}
      description: Parent term
      owners:
        - id: {OWNER_ID}
"""
    )
    with apply_server() as server:
        client = make_tenant_bound_client(server.base_url)
        try:
            remote = capture_remote_for_apply(client, include_glossary_terms=True)
            plan = build_plan_from_yaml(yaml_text, remote)
            result = execute_governance_plan_v3(plan, remote, client, mode=ExecutionMode.APPLY)
        finally:
            client.close()
    assert result.status == "applied"
    assert TERM_PARENT in server.state.glossary_terms_by_id
