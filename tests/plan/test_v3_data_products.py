"""Tests for governance plan v3 Data Products."""

from __future__ import annotations

from purview_governance.config.models_v3 import (
    CONFIG_API_VERSION_V3,
    UNIFIED_CATALOG_SURFACE,
)
from purview_governance.config.service_v3 import validate_config_v3_text
from purview_governance.plan import build_governance_plan_v3
from purview_governance.plan.identity import compute_target_context_identity_v3
from purview_governance.remote_state.models import UnsupportedConfigurableField
from purview_governance.remote_state.models_v3 import (
    NormalizedBusinessDomain,
    NormalizedDataProduct,
    RemoteTargetContextV3,
    UninterpretedBusinessDomain,
    build_remote_state_v3,
)

TENANT_ID = "20000000-0000-4000-8000-000000000001"
ENDPOINT = "https://catalog.purview.azure.com"
DOMAIN_A = "10000000-0000-4000-8000-000000000001"
DOMAIN_B = "10000000-0000-4000-8000-000000000002"
DOMAIN_C = "10000000-0000-4000-8000-000000000003"
DOMAIN_REMOTE = "10000000-0000-4000-8000-000000000099"
DOMAIN_UNINTERPRETED = "10000000-0000-4000-8000-000000000088"
DP_A = "40000000-0000-4000-8000-000000000001"
DP_B = "40000000-0000-4000-8000-000000000002"
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


def _business_domain_yaml(
    *,
    domain_id: str,
    name: str,
    parent_id: str | None = None,
) -> str:
    parent_line = f"\n      parentId: {parent_id}" if parent_id else ""
    return f"""
  - type: businessDomain
    id: {domain_id}
    properties:
      name: {name}
      status: PUBLISHED
      type: DataDomain{parent_line}
"""


def _data_product_yaml(
    *,
    product_id: str = DP_A,
    name: str = "sales-product",
    domain: str = DOMAIN_A,
) -> str:
    return f"""
  - type: dataProduct
    id: {product_id}
    properties:
      name: {name}
      domain: {domain}
      type: Master
      description: Product description
      businessUse: Primary business use
      owners:
        - id: {OWNER_A}
"""


def _shape_b_remote(
    *,
    domains: tuple[NormalizedBusinessDomain, ...] = (),
    uninterpreted_domains: tuple[UninterpretedBusinessDomain, ...] = (),
    products: tuple[NormalizedDataProduct, ...] = (),
) -> build_remote_state_v3:
    return build_remote_state_v3(
        domains,
        uninterpreted_domains,
        _target_context(),
        data_products=products,
        captured_resource_types=("businessDomain", "dataProduct"),
    )


def _shape_a_remote(
    *,
    domains: tuple[NormalizedBusinessDomain, ...] = (),
) -> build_remote_state_v3:
    return build_remote_state_v3(domains, (), _target_context())


def _normalized_domain(domain_id: str, name: str) -> NormalizedBusinessDomain:
    return NormalizedBusinessDomain(
        id=domain_id,
        properties={
            "name": name,
            "status": "PUBLISHED",
            "type": "DataDomain",
        },
    )


def _normalized_product(
    product_id: str,
    *,
    domain: str = DOMAIN_A,
    name: str = "sales-product",
) -> NormalizedDataProduct:
    return NormalizedDataProduct(
        id=product_id,
        properties={
            "name": name,
            "domain": domain,
            "type": "Master",
            "description": "Product description",
            "businessUse": "Primary business use",
            "owners": [{"id": OWNER_A}],
        },
        safety_properties={"status": "DRAFT"},
    )


def _dp_item(plan, product_id: str):
    for item in plan.change_set.items:
        if item.resource_type == "dataProduct" and item.id == product_id:
            return item
    raise AssertionError(f"missing data product diff item for {product_id}")


def test_domain_dependency_case_a_remote_domain_satisfied() -> None:
    config = validate_config_v3_text(
        _config_header() + _data_product_yaml(domain=DOMAIN_REMOTE),
        format_hint="yaml",
    )
    remote = _shape_b_remote(domains=(_normalized_domain(DOMAIN_REMOTE, "remote-domain"),))
    plan = build_governance_plan_v3(config, remote)
    item = _dp_item(plan, DP_A)
    assert item.outcome == "create"
    assert plan.execution_eligibility == "ready"


def test_domain_dependency_case_b_depends_on_create() -> None:
    config = validate_config_v3_text(
        _config_header()
        + _business_domain_yaml(domain_id=DOMAIN_A, name="new-domain")
        + _data_product_yaml(domain=DOMAIN_A),
        format_hint="yaml",
    )
    remote = _shape_b_remote()
    plan = build_governance_plan_v3(config, remote)
    item = _dp_item(plan, DP_A)
    assert item.outcome == "create"
    assert plan.execution_eligibility == "ready"
    assert plan.operations[0].resource_type == "businessDomain"
    assert plan.operations[0].action == "create"
    assert plan.operations[1].resource_type == "dataProduct"
    assert plan.operations[1].action == "create"


def test_domain_dependency_case_c_blocked_create() -> None:
    config = validate_config_v3_text(
        _config_header()
        + _business_domain_yaml(domain_id=DOMAIN_A, name="taken-name")
        + _data_product_yaml(domain=DOMAIN_A),
        format_hint="yaml",
    )
    remote = _shape_b_remote(
        domains=(_normalized_domain(DOMAIN_B, "taken-name"),),
    )
    plan = build_governance_plan_v3(config, remote)
    item = _dp_item(plan, DP_A)
    assert item.outcome == "blocked"
    assert any(reason.code == "plan.domain_dependency_blocked" for reason in item.reasons)
    assert plan.execution_eligibility == "blocked"


def test_domain_dependency_case_d_unresolved_domain() -> None:
    config = validate_config_v3_text(
        _config_header() + _data_product_yaml(domain=DOMAIN_C),
        format_hint="yaml",
    )
    remote = _shape_b_remote()
    plan = build_governance_plan_v3(config, remote)
    item = _dp_item(plan, DP_A)
    assert item.outcome == "blocked"
    assert any(reason.code == "plan.domain_unresolved" for reason in item.reasons)


def test_domain_dependency_case_e_uninterpreted_domain() -> None:
    config = validate_config_v3_text(
        _config_header() + _data_product_yaml(domain=DOMAIN_UNINTERPRETED),
        format_hint="yaml",
    )
    remote = _shape_b_remote(
        uninterpreted_domains=(
            UninterpretedBusinessDomain(
                id=DOMAIN_UNINTERPRETED,
                reason_code="remote_state.hierarchy_ambiguous",
            ),
        ),
    )
    plan = build_governance_plan_v3(config, remote)
    item = _dp_item(plan, DP_A)
    assert item.outcome == "blocked"
    assert any(reason.code == "plan.domain_uninterpreted" for reason in item.reasons)


def test_remote_capture_incomplete_shape_a_blocks_mutating_data_products() -> None:
    config = validate_config_v3_text(
        _config_header() + _data_product_yaml(),
        format_hint="yaml",
    )
    remote = _shape_a_remote(domains=(_normalized_domain(DOMAIN_A, "root-domain"),))
    plan = build_governance_plan_v3(config, remote)
    item = _dp_item(plan, DP_A)
    assert item.outcome == "blocked"
    assert any(reason.code == "plan.remote_capture_incomplete" for reason in item.reasons)
    assert plan.execution_eligibility == "blocked"


def test_operation_order_business_domains_before_data_products() -> None:
    config = validate_config_v3_text(
        _config_header()
        + _business_domain_yaml(domain_id=DOMAIN_A, name="new-domain")
        + _data_product_yaml(product_id=DP_A, domain=DOMAIN_A, name="new-product")
        + _data_product_yaml(product_id=DP_B, domain=DOMAIN_A, name="renamed-product"),
        format_hint="yaml",
    )
    remote = _shape_b_remote(
        products=(_normalized_product(DP_B, domain=DOMAIN_A, name="existing-product"),),
    )
    plan = build_governance_plan_v3(config, remote)
    resource_types = [operation.resource_type for operation in plan.operations]
    assert resource_types.index("businessDomain") < resource_types.index("dataProduct")
    bd_ops = [op for op in plan.operations if op.resource_type == "businessDomain"]
    dp_ops = [op for op in plan.operations if op.resource_type == "dataProduct"]
    assert [op.action for op in bd_ops] == ["create"]
    assert sorted(op.action for op in dp_ops) == ["create", "replace"]


def test_blocked_business_domain_replace_does_not_block_data_product() -> None:
    config = validate_config_v3_text(
        _config_header()
        + _business_domain_yaml(domain_id=DOMAIN_A, name="renamed-domain")
        + _data_product_yaml(domain=DOMAIN_A),
        format_hint="yaml",
    )
    remote = _shape_b_remote(
        domains=(
            NormalizedBusinessDomain(
                id=DOMAIN_A,
                properties={
                    "name": "root-domain",
                    "status": "PUBLISHED",
                    "type": "DataDomain",
                },
                unsupported_configurable_fields=(
                    UnsupportedConfigurableField(
                        path="/managedAttributes",
                        value_identity="sha256:0000000000000000000000000000000000000000000000000000000000000000",
                    ),
                ),
            ),
        ),
    )
    plan = build_governance_plan_v3(config, remote)
    bd_item = next(item for item in plan.change_set.items if item.resource_type == "businessDomain")
    dp_item = _dp_item(plan, DP_A)
    assert bd_item.outcome == "blocked"
    assert dp_item.outcome == "create"
    assert plan.execution_eligibility == "blocked"
    assert any(op.resource_type == "dataProduct" for op in plan.operations)
