"""Tests for governance plan v3 Glossary Terms."""

from __future__ import annotations

from purview_governance.config.models_v3 import CONFIG_API_VERSION_V3, UNIFIED_CATALOG_SURFACE
from purview_governance.config.service_v3 import validate_config_v3_text
from purview_governance.plan import build_governance_plan_v3
from purview_governance.plan.identity import compute_target_context_identity_v3
from purview_governance.plan.models_v3 import (
    change_set_v3_from_document,
    desired_state_v3_from_document,
    operations_v3_from_document,
)
from purview_governance.remote_state.models_v3 import (
    NormalizedBusinessDomain,
    NormalizedGlossaryTerm,
    RemoteTargetContextV3,
    UninterpretedGlossaryTerm,
    build_remote_state_v3,
)

TENANT_ID = "20000000-0000-4000-8000-000000000001"
ENDPOINT = "https://catalog.purview.azure.com"
DOMAIN_A = "10000000-0000-4000-8000-000000000001"
DOMAIN_REMOTE = "10000000-0000-4000-8000-000000000099"
GT_ROOT = "50000000-0000-4000-8000-000000000001"
GT_CHILD = "50000000-0000-4000-8000-000000000002"
GT_CYCLE_A = "50000000-0000-4000-8000-000000000010"
GT_CYCLE_B = "50000000-0000-4000-8000-000000000011"
OWNER_A = "30000000-0000-4000-8000-000000000001"


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


def _config_header() -> str:
    return f"""
apiVersion: {CONFIG_API_VERSION_V3}
target:
  surface: {UNIFIED_CATALOG_SURFACE}
  tenantId: {TENANT_ID}
authentication:
  strategy: defaultAzureCredential
resources:
"""


def _business_domain_yaml(domain_id: str = DOMAIN_A) -> str:
    return f"""
  - type: businessDomain
    id: {domain_id}
    properties:
      name: root-domain
      status: PUBLISHED
      type: DataDomain
"""


def _glossary_term_yaml(
    *,
    term_id: str = GT_ROOT,
    parent_id: str | None = None,
    acronyms_yaml: str = "",
) -> str:
    parent_line = f"\n      parentId: {parent_id}" if parent_id else ""
    return f"""
  - type: glossaryTerm
    id: {term_id}
    properties:
      name: revenue
      domain: {DOMAIN_A}
      description: Revenue term
      owners:
        - id: {OWNER_A}{parent_line}{acronyms_yaml}
"""


def _shape_d_remote(
    *,
    domains: tuple[NormalizedBusinessDomain, ...] = (),
    terms: tuple[NormalizedGlossaryTerm, ...] = (),
    uninterpreted_terms: tuple[UninterpretedGlossaryTerm, ...] = (),
) -> build_remote_state_v3:
    return build_remote_state_v3(
        domains,
        (),
        _target_context(),
        glossary_terms=terms,
        uninterpreted_glossary_terms=uninterpreted_terms,
        captured_resource_types=("businessDomain", "glossaryTerm"),
    )


def _normalized_domain(domain_id: str) -> NormalizedBusinessDomain:
    return NormalizedBusinessDomain(
        id=domain_id,
        properties={"name": "root-domain", "status": "PUBLISHED", "type": "DataDomain"},
    )


def _normalized_term(
    term_id: str,
    *,
    parent_id: str | None = None,
    domain: str = DOMAIN_A,
    status: str = "DRAFT",
) -> NormalizedGlossaryTerm:
    properties: dict[str, object] = {
        "name": "revenue",
        "domain": domain,
        "description": "Revenue term",
        "owners": [{"id": OWNER_A}],
    }
    if parent_id is not None:
        properties["parentId"] = parent_id
    return NormalizedGlossaryTerm(
        id=term_id,
        properties=properties,
        safety_properties={"status": status},
    )


def _gt_item(plan, term_id: str):
    for item in plan.change_set.items:
        if item.resource_type == "glossaryTerm" and item.id == term_id:
            return item
    raise AssertionError(f"missing glossary term item {term_id}")


def test_glossary_term_create_orders_parent_before_child() -> None:
    config = validate_config_v3_text(
        _config_header()
        + _business_domain_yaml()
        + _glossary_term_yaml(term_id=GT_ROOT)
        + _glossary_term_yaml(term_id=GT_CHILD, parent_id=GT_ROOT),
        format_hint="yaml",
    )
    remote = _shape_d_remote(domains=(_normalized_domain(DOMAIN_A),))
    plan = build_governance_plan_v3(config, remote)
    gt_ops = [op for op in plan.operations if op.resource_type == "glossaryTerm"]
    assert [op.id for op in gt_ops] == [GT_ROOT, GT_CHILD]
    assert plan.execution_eligibility == "ready"


def test_glossary_term_remote_capture_incomplete_blocks() -> None:
    config = validate_config_v3_text(
        _config_header() + _business_domain_yaml() + _glossary_term_yaml(),
        format_hint="yaml",
    )
    remote = build_remote_state_v3(
        (_normalized_domain(DOMAIN_A),),
        (),
        _target_context(),
    )
    plan = build_governance_plan_v3(config, remote)
    item = _gt_item(plan, GT_ROOT)
    assert item.outcome == "blocked"
    assert any(reason.code == "plan.remote_capture_incomplete" for reason in item.reasons)


def test_glossary_term_resultant_hierarchy_cycle_is_blocked() -> None:
    """Desired child references remote parent in a remote-only cycle."""
    config = validate_config_v3_text(
        _config_header()
        + _business_domain_yaml()
        + _glossary_term_yaml(term_id=GT_CHILD, parent_id=GT_CYCLE_A),
        format_hint="yaml",
    )
    remote = _shape_d_remote(
        domains=(_normalized_domain(DOMAIN_A),),
        terms=(
            _normalized_term(GT_CYCLE_A, parent_id=GT_CYCLE_B),
            _normalized_term(GT_CYCLE_B, parent_id=GT_CYCLE_A),
        ),
    )
    plan = build_governance_plan_v3(config, remote)
    item = _gt_item(plan, GT_CHILD)
    assert item.outcome == "blocked"
    assert any(reason.code == "plan.glossary_term_hierarchy_cycle" for reason in item.reasons)


def test_unrelated_remote_cycle_does_not_block_independent_desired_root() -> None:
    config = validate_config_v3_text(
        _config_header() + _business_domain_yaml() + _glossary_term_yaml(term_id=GT_ROOT),
        format_hint="yaml",
    )
    remote = _shape_d_remote(
        domains=(_normalized_domain(DOMAIN_A),),
        terms=(
            _normalized_term(GT_CYCLE_A, parent_id=GT_CYCLE_B),
            _normalized_term(GT_CYCLE_B, parent_id=GT_CYCLE_A),
        ),
    )
    plan = build_governance_plan_v3(config, remote)
    item = _gt_item(plan, GT_ROOT)
    assert item.outcome == "create"


def test_desired_root_override_does_not_fall_back_to_remote_parent() -> None:
    config = validate_config_v3_text(
        _config_header() + _business_domain_yaml() + _glossary_term_yaml(term_id=GT_ROOT),
        format_hint="yaml",
    )
    remote = _shape_d_remote(
        domains=(_normalized_domain(DOMAIN_A),),
        terms=(_normalized_term(GT_ROOT, parent_id=GT_CHILD), _normalized_term(GT_CHILD)),
    )
    plan = build_governance_plan_v3(config, remote)
    item = _gt_item(plan, GT_ROOT)
    assert item.outcome == "replace"
    assert any(reason.code == "properties.parentId.changed" for reason in item.reasons)


def test_plan_document_roundtrip_parsers_include_glossary_terms() -> None:
    config = validate_config_v3_text(
        _config_header()
        + _business_domain_yaml()
        + _glossary_term_yaml(acronyms_yaml="\n      acronyms:\n        - REV"),
        format_hint="yaml",
    )
    remote = _shape_d_remote(
        domains=(_normalized_domain(DOMAIN_A),),
        terms=(_normalized_term(GT_ROOT, status="DRAFT"),),
    )
    plan = build_governance_plan_v3(config, remote)
    document = plan.to_document()
    desired = desired_state_v3_from_document(document["desiredState"])
    assert len(desired.glossary_terms) == 1
    assert desired.glossary_terms[0].acronyms == ("REV",)
    change_set = change_set_v3_from_document(document["changeSet"])
    assert any(item.resource_type == "glossaryTerm" for item in change_set.items)
    operations = operations_v3_from_document(document["operations"])
    assert any(op.resource_type == "glossaryTerm" for op in operations)


def test_glossary_term_schema_has_no_status_field() -> None:
    config = validate_config_v3_text(
        _config_header() + _business_domain_yaml() + _glossary_term_yaml(),
        format_hint="yaml",
    )
    term = config.glossary_terms[0]
    assert not hasattr(term, "status")
