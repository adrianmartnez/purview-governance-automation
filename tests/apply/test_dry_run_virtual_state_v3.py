"""VirtualExecutionStateV3 dependency simulation for apply/v3."""

from __future__ import annotations

from purview_governance.apply.payloads_v3 import (
    FAILURE_SEMANTICS_UNVERIFIED,
    VirtualExecutionStateV3,
    check_plan_dependencies,
    simulate_virtual_state,
    validate_operation_capability,
)
from purview_governance.remote_state.models_v3 import (
    NormalizedBusinessDomain,
    build_remote_state_v3,
)
from tests.apply.helpers_v3 import (
    DOMAIN_A,
    DOMAIN_NEW,
    OWNER_ID,
    PRODUCT_A,
    TERM_CHILD,
    TERM_PARENT,
    base_config_header,
    build_plan_from_yaml,
    target_context,
)


def _remote_with_domain() -> build_remote_state_v3:
    return build_remote_state_v3(
        (
            NormalizedBusinessDomain(
                id=DOMAIN_A,
                properties={"name": "root-domain", "status": "PUBLISHED", "type": "DataDomain"},
            ),
        ),
        (),
        target_context(),
        captured_resource_types=("businessDomain", "glossaryTerm"),
    )


def test_virtual_state_multi_op_dry_run_dependency() -> None:
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
    remote = _remote_with_domain()
    plan = build_plan_from_yaml(yaml_text, remote)
    assert plan.execution_eligibility == "ready"
    virtual = simulate_virtual_state(plan, remote)
    assert TERM_PARENT in virtual.glossary_term_ids
    assert check_plan_dependencies(plan, virtual) is None


def test_dependency_failure_when_parent_missing() -> None:
    yaml_text = (
        base_config_header()
        + f"""
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
    remote = _remote_with_domain()
    plan = build_plan_from_yaml(yaml_text, remote)
    assert plan.execution_eligibility == "blocked"
    virtual = VirtualExecutionStateV3.from_fresh_remote(remote)
    assert check_plan_dependencies(plan, virtual) is None


def test_bd_create_capability_blocked() -> None:
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
    remote = build_remote_state_v3((), (), target_context())
    plan = build_plan_from_yaml(yaml_text, remote)
    virtual = simulate_virtual_state(plan, remote)
    operation = plan.operations[0]
    code = validate_operation_capability(operation, plan, remote, virtual)
    assert code == FAILURE_SEMANTICS_UNVERIFIED


def test_dp_domain_dependency_on_bd_create() -> None:
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
    id: {PRODUCT_A}
    properties:
      name: sales-product
      domain: {DOMAIN_NEW}
      type: Master
      description: Product description
      businessUse: Primary business use
      owners:
        - id: {OWNER_ID}
"""
    )
    remote = build_remote_state_v3(
        (
            NormalizedBusinessDomain(
                id=DOMAIN_A,
                properties={"name": "root-domain", "status": "PUBLISHED", "type": "DataDomain"},
            ),
        ),
        (),
        target_context(),
        captured_resource_types=("businessDomain", "dataProduct"),
    )
    plan = build_plan_from_yaml(yaml_text, remote)
    assert plan.execution_eligibility == "ready"
    virtual = simulate_virtual_state(plan, remote)
    dp_op = next(op for op in plan.operations if op.resource_type == "dataProduct")
    code = validate_operation_capability(dp_op, plan, remote, virtual)
    assert code == FAILURE_SEMANTICS_UNVERIFIED
