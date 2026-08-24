"""Deterministic desired-vs-remote diff for Business Domains (v3)."""

from __future__ import annotations

from typing import Any

from purview_governance.desired.models_v3 import BusinessDomainDesiredState, DesiredStateV3
from purview_governance.diff.data_product import diff_data_products
from purview_governance.diff.models import DiffDocument, DiffOutcome, DiffReason
from purview_governance.diff.models_v3 import DiffBusinessDomainItem, DiffDataProductItem
from purview_governance.diff.reasons import reason, sort_reasons
from purview_governance.remote_state.canonical import canonical_json_scalar
from purview_governance.remote_state.models import UnsupportedConfigurableField
from purview_governance.remote_state.models_v3 import (
    NormalizedBusinessDomain,
    RemoteStateV3,
    UninterpretedBusinessDomain,
)


def _unsupported_configurable_reasons(
    fields: tuple[UnsupportedConfigurableField, ...],
) -> list[DiffReason]:
    return [
        reason("remote.unsupported_configurable_field", field.path)
        for field in sorted(fields, key=lambda item: item.path)
    ]


def _remote_parent_id(properties: dict[str, Any]) -> str | None:
    if "parentId" not in properties:
        return None
    return properties["parentId"]


def _remote_description(properties: dict[str, Any]) -> str | None:
    if "description" not in properties:
        return None
    return properties["description"]


def _remote_is_restricted(properties: dict[str, Any]) -> bool | None:
    if "isRestricted" not in properties:
        return None
    return properties["isRestricted"]


def _property_change_reasons(
    desired: BusinessDomainDesiredState,
    remote: NormalizedBusinessDomain,
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

    desired_description = desired.description
    remote_description = _remote_description(remote_props)
    if desired_description != remote_description:
        reasons.append(
            reason(
                "properties.description.changed",
                "/properties/description",
                before=canonical_json_scalar(remote_description),
                after=canonical_json_scalar(desired_description),
            )
        )

    desired_parent = desired.parent_id
    remote_parent = _remote_parent_id(remote_props)
    if desired_parent != remote_parent:
        reasons.append(
            reason(
                "properties.parentId.changed",
                "/properties/parentId",
                before=canonical_json_scalar(remote_parent),
                after=canonical_json_scalar(desired_parent),
            )
        )

    if desired.status != remote_props["status"]:
        reasons.append(
            reason(
                "properties.status.changed",
                "/properties/status",
                before=remote_props["status"],
                after=desired.status,
            )
        )

    if desired.domain_type != remote_props["type"]:
        reasons.append(
            reason(
                "properties.type.changed",
                "/properties/type",
                before=remote_props["type"],
                after=desired.domain_type,
            )
        )

    if desired.is_restricted is not None:
        remote_restricted = _remote_is_restricted(remote_props)
        if desired.is_restricted != remote_restricted:
            reasons.append(
                reason(
                    "properties.isRestricted.changed",
                    "/properties/isRestricted",
                    before=canonical_json_scalar(remote_restricted),
                    after=canonical_json_scalar(desired.is_restricted),
                )
            )

    return reasons


def _compare_matched(
    desired: BusinessDomainDesiredState,
    remote: NormalizedBusinessDomain,
) -> DiffBusinessDomainItem:
    reasons: list[DiffReason] = []
    blocking = False

    if remote.unsupported_configurable_fields:
        blocking = True
        reasons.extend(_unsupported_configurable_reasons(remote.unsupported_configurable_fields))

    property_reasons = _property_change_reasons(desired, remote)
    if property_reasons:
        reasons.extend(property_reasons)
        if remote.unsupported_configurable_fields:
            blocking = True

    sorted_reasons = sort_reasons(reasons)
    if blocking:
        outcome: DiffOutcome = "blocked"
    elif property_reasons:
        outcome = "replace"
    else:
        outcome = "no-op"

    return DiffBusinessDomainItem(
        id=desired.id,
        resource_type="businessDomain",
        outcome=outcome,
        reasons=sorted_reasons,
    )


def _item_for_uninterpreted(
    item: UninterpretedBusinessDomain,
    *,
    has_desired: bool,
) -> DiffBusinessDomainItem | None:
    if item.id is None:
        return None
    reasons: list[DiffReason] = [reason(item.reason_code, "/")]
    if not has_desired:
        reasons.append(reason("remote.absent_desired", "/"))
    return DiffBusinessDomainItem(
        id=item.id,
        resource_type="businessDomain",
        outcome="blocked",
        reasons=sort_reasons(reasons),
    )


def _item_remote_only(remote: NormalizedBusinessDomain) -> DiffBusinessDomainItem:
    reasons = _unsupported_configurable_reasons(remote.unsupported_configurable_fields)
    reasons.append(reason("remote.absent_desired", "/"))
    return DiffBusinessDomainItem(
        id=remote.id,
        resource_type="businessDomain",
        outcome="remote-only",
        reasons=sort_reasons(reasons),
    )


def _item_create(
    desired: BusinessDomainDesiredState,
    *,
    name_conflict: bool,
) -> DiffBusinessDomainItem:
    if name_conflict:
        return DiffBusinessDomainItem(
            id=desired.id,
            resource_type="businessDomain",
            outcome="blocked",
            reasons=sort_reasons(
                [
                    reason(
                        "remote.business_domain_name_conflict",
                        "/properties/name",
                        before=desired.name,
                    ),
                ]
            ),
        )
    return DiffBusinessDomainItem(
        id=desired.id,
        resource_type="businessDomain",
        outcome="create",
        reasons=sort_reasons([reason("desired.absent_remote", "/")]),
    )


def _sort_items(items: list[DiffBusinessDomainItem]) -> tuple[DiffBusinessDomainItem, ...]:
    return tuple(sorted(items, key=lambda item: item.id))


def _diff_business_domains_only(
    desired: DesiredStateV3,
    remote: RemoteStateV3,
) -> tuple[DiffBusinessDomainItem, ...]:
    """Compare desired Business Domains against remote-state/v3 (UUID-only matching)."""
    remote_by_id: dict[str, NormalizedBusinessDomain] = {
        item.id: item for item in remote.business_domains
    }
    uninterpreted_by_id: dict[str, UninterpretedBusinessDomain] = {}
    for item in remote.uninterpreted_business_domains:
        if item.id is not None:
            uninterpreted_by_id[item.id] = item

    name_to_id: dict[str, str] = {}
    for domain in remote.business_domains:
        name_to_id[domain.properties["name"]] = domain.id

    desired_ids = {item.id for item in desired.business_domains}
    items: list[DiffBusinessDomainItem] = []

    for domain in desired.business_domains:
        if domain.id in uninterpreted_by_id:
            item = _item_for_uninterpreted(
                uninterpreted_by_id[domain.id],
                has_desired=True,
            )
            if item is not None:
                items.append(item)
            continue

        remote_domain = remote_by_id.get(domain.id)
        if remote_domain is None:
            name_conflict = domain.name in name_to_id and name_to_id[domain.name] != domain.id
            items.append(_item_create(domain, name_conflict=name_conflict))
            continue

        items.append(_compare_matched(domain, remote_domain))

    for domain_id, remote_domain in remote_by_id.items():
        if domain_id not in desired_ids:
            items.append(_item_remote_only(remote_domain))

    for domain_id, uninterpreted in uninterpreted_by_id.items():
        if domain_id not in desired_ids:
            item = _item_for_uninterpreted(uninterpreted, has_desired=False)
            if item is not None:
                items.append(item)

    return _sort_items(items)


def _combined_sort_key(
    item: DiffBusinessDomainItem | DiffDataProductItem,
) -> tuple[int, str]:
    type_rank = 0 if item.resource_type == "businessDomain" else 1
    return (type_rank, item.id)


def diff_desired_vs_remote_v3(
    desired: DesiredStateV3,
    remote: RemoteStateV3,
) -> DiffDocument:
    """Compare desired Unified Catalog resources against remote-state/v3."""
    domain_items = _diff_business_domains_only(desired, remote)
    product_items = diff_data_products(desired, remote)
    combined = tuple(sorted([*domain_items, *product_items], key=_combined_sort_key))
    return DiffDocument(items=combined)
