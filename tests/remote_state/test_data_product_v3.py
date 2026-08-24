"""Data Product remote-state v3 normalization tests."""

from __future__ import annotations

import pytest
from jsonschema import Draft202012Validator

from purview_governance.plan.identity import compute_target_context_identity_v3
from purview_governance.remote_state.data_product_normalize import normalize_data_product
from purview_governance.remote_state.data_product_policy import (
    DATA_PRODUCT_TYPES,
    REASON_PROVISIONING_BLOCKED,
    REASON_UNSUPPORTED_TYPE,
)
from purview_governance.remote_state.models_v3 import (
    NormalizedDataProduct,
    RemoteTargetContextV3,
    UninterpretedDataProduct,
    build_remote_state_v3,
)
from purview_governance.remote_state.schema import load_remote_state_v3_schema
from purview_governance.unified_catalog.constants import UNIFIED_CATALOG_PRODUCTION_ENDPOINT

TENANT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
DOMAIN_ID = "10000000-0000-4000-8000-000000000001"
PRODUCT_ID = "40000000-0000-4000-8000-000000000001"
OWNER_A = "30000000-0000-4000-8000-000000000001"
OWNER_B = "30000000-0000-4000-8000-000000000002"


def _target() -> RemoteTargetContextV3:
    endpoint = UNIFIED_CATALOG_PRODUCTION_ENDPOINT
    return RemoteTargetContextV3(
        surface="unifiedCatalog",
        tenant_id=TENANT,
        endpoint=endpoint,
        identity=compute_target_context_identity_v3(
            surface="unifiedCatalog",
            tenant_id=TENANT,
            endpoint=endpoint,
        ),
    )


def _raw_data_product(
    *,
    product_type: str = "Master",
    provisioning_state: str | None = None,
    owners: list[dict[str, str]] | None = None,
    audience: list[str] | None = None,
    system_data: dict[str, object] | None = None,
) -> dict[str, object]:
    raw: dict[str, object] = {
        "id": PRODUCT_ID,
        "name": "sales-product",
        "domain": DOMAIN_ID,
        "type": product_type,
        "description": "Product description",
        "businessUse": "Primary business use",
        "status": "DRAFT",
        "contacts": {
            "owner": owners if owners is not None else [{"id": OWNER_A}],
        },
    }
    if audience is not None:
        raw["audience"] = audience
    if provisioning_state is not None or system_data is not None:
        sd = dict(system_data or {})
        if provisioning_state is not None:
            sd["provisioningState"] = provisioning_state
        raw["systemData"] = sd
    return raw


@pytest.mark.parametrize("product_type", sorted(DATA_PRODUCT_TYPES))
def test_normalize_all_official_data_product_types(product_type: str) -> None:
    result = normalize_data_product(_raw_data_product(product_type=product_type))
    assert isinstance(result, NormalizedDataProduct)
    assert result.properties["type"] == product_type


def test_normalize_unknown_type_is_uninterpreted() -> None:
    result = normalize_data_product(_raw_data_product(product_type="UnsupportedType"))
    assert isinstance(result, UninterpretedDataProduct)
    assert result.reason_code == REASON_UNSUPPORTED_TYPE


def test_normalize_owner_ids_are_canonicalized_by_id() -> None:
    result = normalize_data_product(
        _raw_data_product(
            owners=[
                {"id": OWNER_B},
                {"id": OWNER_A, "description": "Primary owner"},
            ]
        )
    )
    assert isinstance(result, NormalizedDataProduct)
    owners = result.properties["owners"]
    assert [owner["id"] for owner in owners] == sorted([OWNER_A, OWNER_B])
    assert owners[0]["id"] == OWNER_A
    assert owners[0]["description"] == "Primary owner"


def test_normalize_audience_is_canonicalized_alphabetically() -> None:
    result = normalize_data_product(
        _raw_data_product(audience=["Executive", "DataEngineer", "DataAnalyst"])
    )
    assert isinstance(result, NormalizedDataProduct)
    assert result.properties["audience"] == ["DataAnalyst", "DataEngineer", "Executive"]


@pytest.mark.parametrize("provisioning_state", ["SoftDeleted", "Unknown"])
def test_normalize_provisioning_state_blocked(provisioning_state: str) -> None:
    result = normalize_data_product(_raw_data_product(provisioning_state=provisioning_state))
    assert isinstance(result, UninterpretedDataProduct)
    assert result.reason_code == REASON_PROVISIONING_BLOCKED


def test_system_data_timestamps_do_not_affect_material_identity() -> None:
    base = _raw_data_product()
    with_ts = _raw_data_product(
        system_data={
            "createdAt": "1970-01-01T00:00:00.000Z",
            "createdBy": "00000000-0000-0000-0000-000000000001",
            "lastModifiedAt": "2020-01-01T00:00:00.000Z",
            "lastModifiedBy": "11111111-1111-1111-1111-111111111111",
        }
    )
    norm_a = normalize_data_product(base)
    norm_b = normalize_data_product(with_ts)
    assert isinstance(norm_a, NormalizedDataProduct)
    assert isinstance(norm_b, NormalizedDataProduct)
    state_a = build_remote_state_v3(
        (),
        (),
        _target(),
        data_products=(norm_a,),
        captured_resource_types=("businessDomain", "dataProduct"),
    )
    state_b = build_remote_state_v3(
        (),
        (),
        _target(),
        data_products=(norm_b,),
        captured_resource_types=("businessDomain", "dataProduct"),
    )
    assert state_a.material_state_identity == state_b.material_state_identity


def test_remote_state_shape_a_schema_validation() -> None:
    product = normalize_data_product(_raw_data_product())
    assert isinstance(product, NormalizedDataProduct)
    state = build_remote_state_v3((), (), _target(), data_products=(product,))
    doc = state.to_document()
    assert "capturedResourceTypes" not in doc
    assert "dataProducts" not in doc
    validator = Draft202012Validator(load_remote_state_v3_schema())
    assert validator.is_valid(doc)


def test_remote_state_shape_b_schema_validation() -> None:
    product = normalize_data_product(_raw_data_product())
    assert isinstance(product, NormalizedDataProduct)
    state = build_remote_state_v3(
        (),
        (),
        _target(),
        data_products=(product,),
        captured_resource_types=("businessDomain", "dataProduct"),
    )
    doc = state.to_document()
    assert doc["capturedResourceTypes"] == ["businessDomain", "dataProduct"]
    assert len(doc["dataProducts"]) == 1
    assert doc["uninterpretedDataProducts"] == []
    validator = Draft202012Validator(load_remote_state_v3_schema())
    assert validator.is_valid(doc)
