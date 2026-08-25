"""Payload materialization and capability gates for apply/v3."""

from __future__ import annotations

from purview_governance.apply.payloads_v3 import (
    FAILURE_SEMANTICS_UNVERIFIED,
    materialize_mutation_intents_v3,
    validate_operation_capability,
)
from purview_governance.remote_state.models_v3 import (
    NormalizedBusinessDomain,
    build_remote_state_v3,
)
from tests.apply.helpers_v3 import (
    DOMAIN_A,
    DOMAIN_B,
    DOMAIN_NEW,
    OWNER_ID,
    TERM_PARENT,
    base_config_header,
    build_plan_from_yaml,
    target_context,
)


def test_bd_create_capability_gate() -> None:
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
    from purview_governance.apply.payloads_v3 import VirtualExecutionStateV3

    virtual = VirtualExecutionStateV3.from_fresh_remote(remote)
    code = validate_operation_capability(plan.operations[0], plan, remote, virtual)
    assert code == FAILURE_SEMANTICS_UNVERIFIED


def test_bd_child_to_root_replace_blocked() -> None:
    from purview_governance.remote_state.models_v3 import (
        NormalizedBusinessDomain,
        build_remote_state_v3,
    )

    yaml_text = (
        base_config_header()
        + f"""
  - type: businessDomain
    id: {DOMAIN_B}
    properties:
      name: child-domain
      status: DRAFT
      type: FunctionalUnit
"""
    )
    remote = build_remote_state_v3(
        (
            NormalizedBusinessDomain(
                id=DOMAIN_A,
                properties={"name": "root-domain", "status": "PUBLISHED", "type": "DataDomain"},
            ),
            NormalizedBusinessDomain(
                id=DOMAIN_B,
                properties={
                    "name": "child-domain",
                    "status": "DRAFT",
                    "type": "FunctionalUnit",
                    "parentId": DOMAIN_A,
                },
            ),
        ),
        (),
        target_context(),
    )
    plan = build_plan_from_yaml(yaml_text, remote)
    from purview_governance.apply.payloads_v3 import VirtualExecutionStateV3

    virtual = VirtualExecutionStateV3.from_fresh_remote(remote)
    replace_op = next(op for op in plan.operations if op.action == "replace")
    code = validate_operation_capability(replace_op, plan, remote, virtual)
    assert code == FAILURE_SEMANTICS_UNVERIFIED


def test_materialize_glossary_term_create_payload() -> None:
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
    remote = build_remote_state_v3(
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
    plan = build_plan_from_yaml(yaml_text, remote)
    from purview_governance.apply.payloads_v3 import PreflightContext, build_fresh_deferred_index

    intents = materialize_mutation_intents_v3(
        plan,
        PreflightContext(
            plan=plan,
            fresh_deferred_index=build_fresh_deferred_index(remote),
            by_sequence={},
        ),
    )
    assert intents[0].action == "create"
    assert intents[0].payload["status"] == "DRAFT"
    assert intents[0].payload["id"] == TERM_PARENT


def test_gt_acronyms_absent_preserve_and_empty_clear() -> None:
    from purview_governance.apply.payloads_v3 import _materialize_glossary_term_replace
    from purview_governance.desired.models_v3 import (
        GlossaryTermDesiredState,
        GlossaryTermOwnerDesiredState,
    )

    raw = {
        "id": TERM_PARENT,
        "name": "parent-term",
        "domain": DOMAIN_A,
        "description": "Parent term",
        "status": "DRAFT",
        "acronyms": ["REV"],
        "contacts": {"owner": [{"id": OWNER_ID}]},
    }
    absent = GlossaryTermDesiredState(
        id=TERM_PARENT,
        name="parent-term-renamed",
        domain=DOMAIN_A,
        description="Parent term",
        owners=(GlossaryTermOwnerDesiredState(id=OWNER_ID),),
        acronyms=None,
    )
    preserved = _materialize_glossary_term_replace(absent, raw)
    assert preserved["acronyms"] == ["REV"]

    cleared = GlossaryTermDesiredState(
        id=TERM_PARENT,
        name="parent-term-renamed",
        domain=DOMAIN_A,
        description="Parent term",
        owners=(GlossaryTermOwnerDesiredState(id=OWNER_ID),),
        acronyms=(),
    )
    emptied = _materialize_glossary_term_replace(cleared, raw)
    assert emptied["acronyms"] == []


def test_bd_is_restricted_false_and_absent_preserve() -> None:
    from purview_governance.apply.payloads_v3 import _materialize_business_domain_replace
    from purview_governance.desired.models_v3 import BusinessDomainDesiredState

    raw = {
        "id": DOMAIN_A,
        "name": "root-domain",
        "status": "PUBLISHED",
        "type": "DataDomain",
        "isRestricted": True,
        "systemData": {"createdBy": "x"},
    }
    explicit_false = BusinessDomainDesiredState(
        id=DOMAIN_A,
        name="root-domain",
        description=None,
        parent_id=None,
        status="PUBLISHED",
        domain_type="DataDomain",
        is_restricted=False,
    )
    payload_false = _materialize_business_domain_replace(explicit_false, raw)
    assert payload_false["isRestricted"] is False

    unmanaged = BusinessDomainDesiredState(
        id=DOMAIN_A,
        name="root-renamed",
        description=None,
        parent_id=None,
        status="PUBLISHED",
        domain_type="DataDomain",
        is_restricted=None,
    )
    payload_keep = _materialize_business_domain_replace(unmanaged, raw)
    assert payload_keep["isRestricted"] is True


def test_dp_endorsed_false_and_audience_empty() -> None:
    from purview_governance.apply.payloads_v3 import _materialize_data_product_replace
    from purview_governance.desired.models_v3 import (
        DataProductDesiredState,
        DataProductOwnerDesiredState,
    )

    raw = {
        "id": "40000000-0000-4000-8000-000000000001",
        "name": "product",
        "domain": DOMAIN_A,
        "type": "Master",
        "description": "d",
        "businessUse": "b",
        "status": "DRAFT",
        "endorsed": True,
        "audience": ["Executive"],
        "contacts": {"owner": [{"id": OWNER_ID}]},
    }
    desired = DataProductDesiredState(
        id="40000000-0000-4000-8000-000000000001",
        name="product",
        domain=DOMAIN_A,
        product_type="Master",
        description="d",
        business_use="b",
        owners=(DataProductOwnerDesiredState(id=OWNER_ID),),
        audience=(),
        endorsed=False,
    )
    payload = _materialize_data_product_replace(desired, raw)
    assert payload["endorsed"] is False
    assert payload["audience"] == []
