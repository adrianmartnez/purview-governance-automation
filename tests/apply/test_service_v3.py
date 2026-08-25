"""Controlled apply/v3 service matrices."""

from __future__ import annotations

from purview_governance.apply import ExecutionMode, execute_governance_plan_v3
from purview_governance.apply.identity import RESULT_API_VERSION_V3
from tests.apply.helpers_v3 import (
    DOMAIN_A,
    DOMAIN_B,
    OWNER_ID,
    TERM_CHILD,
    TERM_PARENT,
    _default_root_domain,
    apply_server,
    base_config_header,
    build_plan_from_yaml,
    capture_remote_for_apply,
    make_tenant_bound_client,
)
from tests.contract.unified_catalog_server import fictional_business_domain_item


def test_dry_run_reaches_ready_zero_writes() -> None:
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
            before = len(server.state.recordings)
            result = execute_governance_plan_v3(plan, remote, client, mode=ExecutionMode.DRY_RUN)
            writes = [r for r in server.state.recordings[before:] if r.method in {"POST", "PUT"}]
        finally:
            client.close()
    assert result.status == "dry-run-ready"
    assert result.api_version == RESULT_API_VERSION_V3
    assert result.writes_attempted == 0
    assert writes == []


def test_term_parent_then_child_apply_sequence() -> None:
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
  - type: glossaryTerm
    id: {TERM_CHILD}
    properties:
      name: child-term
      domain: {DOMAIN_A}
      description: Child term
      owners:
        - id: {OWNER_ID}
      parentId: {TERM_PARENT}
"""
    )
    with apply_server() as server:
        client = make_tenant_bound_client(server.base_url)
        try:
            remote = capture_remote_for_apply(client, include_glossary_terms=True)
            plan = build_plan_from_yaml(yaml_text, remote)
            result = execute_governance_plan_v3(plan, remote, client, mode=ExecutionMode.APPLY)
            posts = [r for r in server.state.recordings if r.method == "POST"]
        finally:
            client.close()
    assert result.status == "applied"
    assert result.writes_performed == 2
    assert len(posts) == 2
    assert all(op.status == "succeeded" for op in result.operations)


def test_bd_child_to_child_replace_apply() -> None:
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
    child = fictional_business_domain_item(
        domain_id=DOMAIN_B,
        name="child-domain",
    )
    child["parentId"] = DOMAIN_A
    child["type"] = "FunctionalUnit"
    child["status"] = "DRAFT"
    with apply_server(enumerate_items=[root, child]) as server:
        client = make_tenant_bound_client(server.base_url)
        try:
            remote = capture_remote_for_apply(client)
            plan = build_plan_from_yaml(yaml_text, remote)
            result = execute_governance_plan_v3(plan, remote, client, mode=ExecutionMode.APPLY)
            puts = [r for r in server.state.recordings if r.method == "PUT"]
        finally:
            client.close()
    assert result.status == "applied"
    assert result.writes_performed == 1
    assert len(puts) == 1
    assert puts[0].path.endswith(DOMAIN_B)


def test_stale_plan_zero_writes() -> None:
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
            server.state.business_domains_by_id["99999999-9999-4999-8999-999999999999"] = {
                "id": "99999999-9999-4999-8999-999999999999",
                "name": "drift-domain",
                "status": "PUBLISHED",
                "type": "DataDomain",
            }
            result = execute_governance_plan_v3(plan, remote, client, mode=ExecutionMode.APPLY)
        finally:
            client.close()
    assert result.status == "stale"
    assert result.writes_attempted == 0
    assert not any(r.method in {"POST", "PUT"} for r in server.state.recordings)


def test_bd_create_in_ready_plan_zero_writes() -> None:
    yaml_text = (
        base_config_header()
        + """
  - type: businessDomain
    id: 10000000-0000-4000-8000-000000000099
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
    assert result.status == "failed-before-write"
    bd_posts = (
        r.method == "POST" and r.path.rsplit("/", 1)[0] == "/businessdomains"
        for r in server.state.recordings
    )
    assert not any(bd_posts)
