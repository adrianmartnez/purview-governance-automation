"""Tests for governance config v3 Data Products."""

from __future__ import annotations

import pytest

from purview_governance.config.diagnostics import ConfigValidationError
from purview_governance.config.models_v3 import (
    CONFIG_API_VERSION_V3,
    MAX_BUSINESS_DOMAINS,
    UNIFIED_CATALOG_SURFACE,
)
from purview_governance.config.service_v3 import validate_config_v3_dict, validate_config_v3_text
from purview_governance.desired.mapping_v3 import desired_state_from_config_v3
from purview_governance.remote_state.data_product_policy import DATA_PRODUCT_TYPES

TENANT_ID = "20000000-0000-4000-8000-000000000001"
DOMAIN_A = "10000000-0000-4000-8000-000000000001"
DOMAIN_B = "10000000-0000-4000-8000-000000000002"
DOMAIN_EXTERNAL = "10000000-0000-4000-8000-0000000000ff"
OWNER_A = "30000000-0000-4000-8000-000000000001"
OWNER_B = "30000000-0000-4000-8000-000000000002"
DP_A = "40000000-0000-4000-8000-000000000001"
DP_B = "40000000-0000-4000-8000-000000000002"
SHARED_ID = "50000000-0000-4000-8000-000000000001"


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


def _data_product_block(
    *,
    product_id: str = DP_A,
    name: str = "sales-product",
    domain: str = DOMAIN_A,
    product_type: str = "Master",
    owners_yaml: str | None = None,
    audience_yaml: str = "",
) -> str:
    if owners_yaml is None:
        owners_yaml = f"""
      owners:
        - id: {OWNER_A}"""
    return f"""
  - type: dataProduct
    id: {product_id}
    properties:
      name: {name}
      domain: {domain}
      type: {product_type}
      description: Product description
      businessUse: Primary business use
{owners_yaml}{audience_yaml}
"""


def _business_domain_block(
    *,
    domain_id: str = DOMAIN_A,
    name: str = "root-domain",
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


@pytest.mark.parametrize("product_type", sorted(DATA_PRODUCT_TYPES))
def test_validate_v3_data_product_accepts_all_official_types(product_type: str) -> None:
    yaml = (
        _config_header() + _business_domain_block() + _data_product_block(product_type=product_type)
    )
    config = validate_config_v3_text(yaml, format_hint="yaml")
    product = config.data_products[0]
    assert product.product_type == product_type


def test_validate_v3_data_product_rejects_unknown_type() -> None:
    yaml = (
        _config_header()
        + _business_domain_block()
        + _data_product_block(product_type="UnsupportedType")
    )
    with pytest.raises(ConfigValidationError, match="config.invalid_syntax"):
        validate_config_v3_text(yaml, format_hint="yaml")


def test_validate_v3_data_product_rejects_duplicate_owner_ids() -> None:
    owners_yaml = f"""
      owners:
        - id: {OWNER_A}
        - id: {OWNER_A}"""
    yaml = (
        _config_header() + _business_domain_block() + _data_product_block(owners_yaml=owners_yaml)
    )
    with pytest.raises(ConfigValidationError, match="duplicate owner id"):
        validate_config_v3_text(yaml, format_hint="yaml")


def test_validate_v3_data_product_rejects_duplicate_audience() -> None:
    audience_yaml = """
      audience:
        - DataEngineer
        - DataEngineer"""
    yaml = (
        _config_header()
        + _business_domain_block()
        + _data_product_block(audience_yaml=audience_yaml)
    )
    with pytest.raises(ConfigValidationError, match="duplicate audience"):
        validate_config_v3_text(yaml, format_hint="yaml")


def _config_document(*resource_docs: dict[str, object]) -> dict[str, object]:
    return {
        "apiVersion": CONFIG_API_VERSION_V3,
        "target": {
            "surface": UNIFIED_CATALOG_SURFACE,
            "tenantId": TENANT_ID,
        },
        "authentication": {"strategy": "defaultAzureCredential"},
        "resources": list(resource_docs),
    }


def _business_domain_doc(
    *,
    domain_id: str = DOMAIN_A,
    name: str = "root-domain",
    parent_id: str | None = None,
) -> dict[str, object]:
    properties: dict[str, object] = {
        "name": name,
        "status": "PUBLISHED",
        "type": "DataDomain",
    }
    if parent_id is not None:
        properties["parentId"] = parent_id
    return {
        "type": "businessDomain",
        "id": domain_id,
        "properties": properties,
    }


def _data_product_doc(
    *,
    product_id: str = DP_A,
    name: str = "sales-product",
    domain: str = DOMAIN_A,
    product_type: str = "Master",
    owners: list[dict[str, str]] | None = None,
    audience: list[str] | None = None,
) -> dict[str, object]:
    properties: dict[str, object] = {
        "name": name,
        "domain": domain,
        "type": product_type,
        "description": "Product description",
        "businessUse": "Primary business use",
        "owners": owners if owners is not None else [{"id": OWNER_A}],
    }
    if audience is not None:
        properties["audience"] = audience
    return {
        "type": "dataProduct",
        "id": product_id,
        "properties": properties,
    }


def test_validate_v3_two_hundred_business_domains_with_data_products_valid() -> None:
    resources: list[dict[str, object]] = []
    for index in range(1, MAX_BUSINESS_DOMAINS + 1):
        domain_id = f"10000000-0000-4000-8000-{index:012x}"
        resources.append(_business_domain_doc(domain_id=domain_id, name=f"domain-{index}"))
    resources.append(
        _data_product_doc(
            product_id=DP_A,
            domain="10000000-0000-4000-8000-000000000001",
        )
    )
    config = validate_config_v3_dict(_config_document(*resources))
    assert len(config.business_domains) == MAX_BUSINESS_DOMAINS
    assert len(config.data_products) == 1


def test_validate_v3_two_hundred_one_business_domains_rejected() -> None:
    resources = [
        _business_domain_doc(
            domain_id=f"10000000-0000-4000-8000-{index:012x}",
            name=f"domain-{index}",
        )
        for index in range(1, MAX_BUSINESS_DOMAINS + 2)
    ]
    with pytest.raises(ConfigValidationError, match="business_domain_count_exceeded"):
        validate_config_v3_dict(_config_document(*resources))


def test_validate_v3_many_data_products_without_count_error() -> None:
    resources: list[dict[str, object]] = [_business_domain_doc()]
    for index in range(1, 250):
        product_id = f"40000000-0000-4000-8000-{index:012x}"
        resources.append(_data_product_doc(product_id=product_id, name=f"product-{index}"))
    config = validate_config_v3_dict(_config_document(*resources))
    assert len(config.data_products) == 249


def test_validate_v3_duplicate_data_product_name_allowed() -> None:
    yaml = (
        _config_header()
        + _business_domain_block()
        + _data_product_block(product_id=DP_A, name="shared-name")
        + _data_product_block(product_id=DP_B, name="shared-name")
    )
    config = validate_config_v3_text(yaml, format_hint="yaml")
    assert {product.name for product in config.data_products} == {"shared-name"}


def test_validate_v3_duplicate_business_domain_name_rejected() -> None:
    yaml = (
        _config_header()
        + _business_domain_block(domain_id=DOMAIN_A, name="shared-name")
        + _business_domain_block(domain_id=DOMAIN_B, name="shared-name")
    )
    with pytest.raises(ConfigValidationError, match="duplicate_business_domain_name"):
        validate_config_v3_text(yaml, format_hint="yaml")


def test_validate_v3_duplicate_data_product_uuid_rejected() -> None:
    yaml = (
        _config_header()
        + _business_domain_block()
        + _data_product_block(product_id=DP_A, name="product-one")
        + _data_product_block(product_id=DP_A, name="product-two")
    )
    with pytest.raises(ConfigValidationError, match="duplicate_data_product_id"):
        validate_config_v3_text(yaml, format_hint="yaml")


def test_validate_v3_same_uuid_for_business_domain_and_data_product_allowed() -> None:
    yaml = (
        _config_header()
        + _business_domain_block(domain_id=SHARED_ID, name="shared-resource")
        + _data_product_block(product_id=SHARED_ID, name="shared-product", domain=DOMAIN_A)
        + _business_domain_block(domain_id=DOMAIN_A, name="root-domain")
    )
    config = validate_config_v3_text(yaml, format_hint="yaml")
    assert len(config.business_domains) == 2
    assert len(config.data_products) == 1
    desired = desired_state_from_config_v3(config)
    assert len(desired.business_domains) == 2
    assert len(desired.data_products) == 1


def test_validate_v3_external_domain_reference_without_desired_domain_valid() -> None:
    yaml = _config_header() + _data_product_block(domain=DOMAIN_EXTERNAL)
    config = validate_config_v3_text(yaml, format_hint="yaml")
    assert config.data_products[0].domain == DOMAIN_EXTERNAL
    assert config.business_domains == ()
