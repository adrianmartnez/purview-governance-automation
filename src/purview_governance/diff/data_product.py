"""Deterministic desired-vs-remote diff for Data Products (v3)."""

from __future__ import annotations

from typing import Any

from purview_governance.desired.models_v3 import DataProductDesiredState, DesiredStateV3
from purview_governance.diff.models import DiffOutcome, DiffReason
from purview_governance.diff.models_v3 import DiffDataProductItem
from purview_governance.diff.reasons import reason, sort_reasons
from purview_governance.remote_state.canonical import canonical_json_scalar
from purview_governance.remote_state.models import UnsupportedConfigurableField
from purview_governance.remote_state.models_v3 import (
    NormalizedDataProduct,
    RemoteStateV3,
    UninterpretedDataProduct,
)


def _unsupported_configurable_reasons(
    fields: tuple[UnsupportedConfigurableField, ...],
) -> list[DiffReason]:
    return [
        reason("remote.unsupported_configurable_field", field.path)
        for field in sorted(fields, key=lambda item: item.path)
    ]


def _owners_document(owners: tuple[Any, ...]) -> list[dict[str, Any]]:
    return [
        {
            "id": owner.id,
            **({"description": owner.description} if owner.description is not None else {}),
        }
        for owner in owners
    ]


def _remote_owners(properties: dict[str, Any]) -> list[dict[str, Any]]:
    return list(properties.get("owners", []))


def _remote_audience(properties: dict[str, Any]) -> list[str] | None:
    if "audience" not in properties:
        return None
    return list(properties["audience"])


def _remote_update_frequency(properties: dict[str, Any]) -> str | None:
    if "updateFrequency" not in properties:
        return None
    return properties["updateFrequency"]


def _remote_endorsed(properties: dict[str, Any]) -> bool | None:
    if "endorsed" not in properties:
        return None
    return properties["endorsed"]


def _status_blocks_replace(remote: NormalizedDataProduct) -> bool:
    status = remote.safety_properties.get("status")
    return status in {"PUBLISHED", "EXPIRED"}


def _property_change_reasons(
    desired: DataProductDesiredState,
    remote: NormalizedDataProduct,
) -> list[DiffReason]:
    reasons: list[DiffReason] = []
    remote_props = remote.properties

    if desired.name != remote_props["name"]:
        reasons.append(
            reason(
                "properties.name.changed",
                "/properties/name",
                before=remote_props["name"],
                after=desired.name,
            )
        )

    if desired.domain != remote_props["domain"]:
        reasons.append(
            reason(
                "properties.domain.changed",
                "/properties/domain",
                before=remote_props["domain"],
                after=desired.domain,
            )
        )

    if desired.product_type != remote_props["type"]:
        reasons.append(
            reason(
                "properties.type.changed",
                "/properties/type",
                before=remote_props["type"],
                after=desired.product_type,
            )
        )

    if desired.description != remote_props["description"]:
        reasons.append(
            reason(
                "properties.description.changed",
                "/properties/description",
                before=canonical_json_scalar(remote_props["description"]),
                after=canonical_json_scalar(desired.description),
            )
        )

    if desired.business_use != remote_props["businessUse"]:
        reasons.append(
            reason(
                "properties.businessUse.changed",
                "/properties/businessUse",
                before=remote_props["businessUse"],
                after=desired.business_use,
            )
        )

    desired_owners = _owners_document(desired.owners)
    remote_owners = _remote_owners(remote_props)
    if desired_owners != remote_owners:
        reasons.append(
            reason(
                "properties.owners.changed",
                "/properties/owners",
                before=canonical_json_scalar(remote_owners),
                after=canonical_json_scalar(desired_owners),
            )
        )

    desired_audience = list(desired.audience) if desired.audience is not None else None
    remote_audience = _remote_audience(remote_props)
    if desired_audience != remote_audience:
        reasons.append(
            reason(
                "properties.audience.changed",
                "/properties/audience",
                before=canonical_json_scalar(remote_audience),
                after=canonical_json_scalar(desired_audience),
            )
        )

    desired_frequency = desired.update_frequency
    remote_frequency = _remote_update_frequency(remote_props)
    if desired_frequency != remote_frequency:
        reasons.append(
            reason(
                "properties.updateFrequency.changed",
                "/properties/updateFrequency",
                before=canonical_json_scalar(remote_frequency),
                after=canonical_json_scalar(desired_frequency),
            )
        )

    desired_endorsed = desired.endorsed
    remote_endorsed = _remote_endorsed(remote_props)
    if desired_endorsed != remote_endorsed:
        reasons.append(
            reason(
                "properties.endorsed.changed",
                "/properties/endorsed",
                before=canonical_json_scalar(remote_endorsed),
                after=canonical_json_scalar(desired_endorsed),
            )
        )

    return reasons


def _compare_matched(
    desired: DataProductDesiredState,
    remote: NormalizedDataProduct,
) -> DiffDataProductItem:
    reasons: list[DiffReason] = []
    blocking = False

    if remote.unsupported_configurable_fields:
        blocking = True
        reasons.extend(_unsupported_configurable_reasons(remote.unsupported_configurable_fields))

    property_reasons = _property_change_reasons(desired, remote)
    if property_reasons:
        reasons.extend(property_reasons)
        if desired.domain != remote.properties["domain"]:
            blocking = True
            reasons.append(reason("plan.domain_move_unverified", "/properties/domain"))
        elif remote.unsupported_configurable_fields:
            blocking = True
        elif _status_blocks_replace(remote):
            blocking = True
            reasons.append(
                reason(
                    "remote.status_blocks_replace",
                    "/safetyProperties/status",
                    before=str(remote.safety_properties.get("status")),
                )
            )

    sorted_reasons = sort_reasons(reasons)
    if blocking:
        outcome: DiffOutcome = "blocked"
    elif property_reasons:
        outcome = "replace"
    else:
        outcome = "no-op"

    return DiffDataProductItem(
        id=desired.id,
        resource_type="dataProduct",
        outcome=outcome,
        reasons=sorted_reasons,
    )


def _item_for_uninterpreted(
    item: UninterpretedDataProduct,
    *,
    has_desired: bool,
) -> DiffDataProductItem | None:
    if item.id is None:
        return None
    reasons: list[DiffReason] = [reason(item.reason_code, "/")]
    if not has_desired:
        reasons.append(reason("remote.absent_desired", "/"))
    return DiffDataProductItem(
        id=item.id,
        resource_type="dataProduct",
        outcome="blocked",
        reasons=sort_reasons(reasons),
    )


def _item_remote_only(remote: NormalizedDataProduct) -> DiffDataProductItem:
    reasons = _unsupported_configurable_reasons(remote.unsupported_configurable_fields)
    reasons.append(reason("remote.absent_desired", "/"))
    return DiffDataProductItem(
        id=remote.id,
        resource_type="dataProduct",
        outcome="remote-only",
        reasons=sort_reasons(reasons),
    )


def _item_create(desired: DataProductDesiredState) -> DiffDataProductItem:
    return DiffDataProductItem(
        id=desired.id,
        resource_type="dataProduct",
        outcome="create",
        reasons=sort_reasons([reason("desired.absent_remote", "/")]),
    )


def _sort_key(item: DiffDataProductItem) -> tuple[int, str]:
    return (1, item.id)


def diff_data_products(
    desired: DesiredStateV3,
    remote: RemoteStateV3,
) -> tuple[DiffDataProductItem, ...]:
    """Compare desired Data Products against remote-state/v3 (UUID-only matching)."""
    remote_by_id: dict[str, NormalizedDataProduct] = {
        item.id: item for item in remote.data_products
    }
    uninterpreted_by_id: dict[str, UninterpretedDataProduct] = {}
    for item in remote.uninterpreted_data_products:
        if item.id is not None:
            uninterpreted_by_id[item.id] = item

    desired_ids = {item.id for item in desired.data_products}
    items: list[DiffDataProductItem] = []

    for product in desired.data_products:
        if product.id in uninterpreted_by_id:
            item = _item_for_uninterpreted(
                uninterpreted_by_id[product.id],
                has_desired=True,
            )
            if item is not None:
                items.append(item)
            continue

        remote_product = remote_by_id.get(product.id)
        if remote_product is None:
            items.append(_item_create(product))
            continue

        items.append(_compare_matched(product, remote_product))

    for product_id, remote_product in remote_by_id.items():
        if product_id not in desired_ids:
            items.append(_item_remote_only(remote_product))

    for product_id, uninterpreted in uninterpreted_by_id.items():
        if product_id not in desired_ids:
            item = _item_for_uninterpreted(uninterpreted, has_desired=False)
            if item is not None:
                items.append(item)

    return tuple(sorted(items, key=_sort_key))
