"""Tests for Data Product diff (v3)."""

from __future__ import annotations

from purview_governance.desired.models_v3 import (
    DataProductDesiredState,
    DataProductOwnerDesiredState,
    DesiredStateV3,
)
from purview_governance.diff.data_product import diff_data_products
from purview_governance.diff.models_v3 import DiffDataProductItem
from purview_governance.plan.identity import compute_target_context_identity_v3
from purview_governance.remote_state.models import UnsupportedConfigurableField
from purview_governance.remote_state.models_v3 import (
    NormalizedDataProduct,
    RemoteStateV3,
    RemoteTargetContextV3,
    UninterpretedDataProduct,
    build_remote_state_v3,
)

TENANT_ID = "20000000-0000-4000-8000-000000000001"
ENDPOINT = "https://catalog.purview.azure.com"
DOMAIN_A = "10000000-0000-4000-8000-000000000001"
DOMAIN_B = "10000000-0000-4000-8000-000000000002"
DP_A = "40000000-0000-4000-8000-000000000001"
DP_B = "40000000-0000-4000-8000-000000000002"
DP_C = "40000000-0000-4000-8000-000000000003"
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


def _remote(
    *,
    products: tuple[NormalizedDataProduct, ...] = (),
    uninterpreted: tuple[UninterpretedDataProduct, ...] = (),
) -> RemoteStateV3:
    return build_remote_state_v3(
        (),
        (),
        _target_context(),
        data_products=products,
        uninterpreted_data_products=uninterpreted,
        captured_resource_types=("businessDomain", "dataProduct"),
    )


def _desired(*products: DataProductDesiredState) -> DesiredStateV3:
    return DesiredStateV3(data_products=tuple(sorted(products, key=lambda item: item.id)))


def _product_desired(
    product_id: str,
    *,
    name: str = "sales-product",
    domain: str = DOMAIN_A,
    product_type: str = "Master",
) -> DataProductDesiredState:
    return DataProductDesiredState(
        id=product_id,
        name=name,
        domain=domain,
        product_type=product_type,  # type: ignore[arg-type]
        description="Product description",
        business_use="Primary business use",
        owners=(DataProductOwnerDesiredState(id=OWNER_A),),
    )


def _normalized(
    product_id: str,
    *,
    name: str = "sales-product",
    domain: str = DOMAIN_A,
    product_type: str = "Master",
    status: str = "DRAFT",
    unsupported: tuple[UnsupportedConfigurableField, ...] = (),
) -> NormalizedDataProduct:
    return NormalizedDataProduct(
        id=product_id,
        properties={
            "name": name,
            "domain": domain,
            "type": product_type,
            "description": "Product description",
            "businessUse": "Primary business use",
            "owners": [{"id": OWNER_A}],
        },
        safety_properties={"status": status},
        unsupported_configurable_fields=unsupported,
    )


def _item(change_set, product_id: str) -> DiffDataProductItem:
    for item in change_set:
        if item.id == product_id:
            return item
    raise AssertionError(f"missing diff item for {product_id}")


def test_create_no_op_replace_blocked_remote_only() -> None:
    desired = _desired(
        _product_desired(DP_A),
        _product_desired(DP_B, name="new-product"),
        _product_desired(DP_C),
    )
    remote = _remote(
        products=(
            _normalized(DP_A),
            _normalized("40000000-0000-4000-8000-000000000099", name="shared-name"),
        ),
        uninterpreted=(
            UninterpretedDataProduct(
                id=DP_C,
                reason_code="remote_state.unsupported_data_product_type",
            ),
        ),
    )
    change_set = diff_data_products(desired, remote)

    assert _item(change_set, DP_A).outcome == "no-op"
    assert _item(change_set, DP_B).outcome == "create"
    assert _item(change_set, DP_C).outcome == "blocked"
    assert _item(change_set, "40000000-0000-4000-8000-000000000099").outcome == "remote-only"


def test_replace_on_property_change() -> None:
    desired = _desired(
        _product_desired(
            DP_A,
            name="renamed-product",
            product_type="Reference",
        ),
    )
    remote = _remote(products=(_normalized(DP_A),))
    item = _item(diff_data_products(desired, remote), DP_A)
    assert item.outcome == "replace"
    codes = {reason.code for reason in item.reasons}
    assert "properties.name.changed" in codes
    assert "properties.type.changed" in codes


def test_domain_move_is_blocked() -> None:
    desired = _desired(_product_desired(DP_A, domain=DOMAIN_B))
    remote = _remote(products=(_normalized(DP_A, domain=DOMAIN_A),))
    item = _item(diff_data_products(desired, remote), DP_A)
    assert item.outcome == "blocked"
    assert any(reason.code == "plan.domain_move_unverified" for reason in item.reasons)


def test_published_status_blocks_replace() -> None:
    desired = _desired(_product_desired(DP_A, name="renamed-product"))
    remote = _remote(products=(_normalized(DP_A, status="PUBLISHED"),))
    item = _item(diff_data_products(desired, remote), DP_A)
    assert item.outcome == "blocked"
    assert any(reason.code == "remote.status_blocks_replace" for reason in item.reasons)


def test_no_name_matching_only_uuid() -> None:
    desired = _desired(_product_desired(DP_B, name="shared-name"))
    remote = _remote(products=(_normalized(DP_A, name="shared-name"),))
    change_set = diff_data_products(desired, remote)

    assert _item(change_set, DP_B).outcome == "create"
    assert _item(change_set, DP_A).outcome == "remote-only"


def test_blocked_on_unsupported_configurable() -> None:
    desired = _desired(_product_desired(DP_A))
    remote = _remote(
        products=(
            _normalized(
                DP_A,
                unsupported=(
                    UnsupportedConfigurableField(
                        path="/managedAttributes",
                        value_identity="sha256:0000000000000000000000000000000000000000000000000000000000000000",
                    ),
                ),
            ),
        ),
    )
    item = _item(diff_data_products(desired, remote), DP_A)
    assert item.outcome == "blocked"
    assert any(reason.code == "remote.unsupported_configurable_field" for reason in item.reasons)
