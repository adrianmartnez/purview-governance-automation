"""Deterministic desired-vs-remote diff for Glossary Terms (v3)."""

from __future__ import annotations

from typing import Any

from purview_governance.desired.models_v3 import DesiredStateV3, GlossaryTermDesiredState
from purview_governance.diff.models import DiffOutcome, DiffReason
from purview_governance.diff.models_v3 import DiffGlossaryTermItem
from purview_governance.diff.reasons import reason, sort_reasons
from purview_governance.remote_state.canonical import canonical_json_scalar
from purview_governance.remote_state.models import UnsupportedConfigurableField
from purview_governance.remote_state.models_v3 import (
    NormalizedGlossaryTerm,
    RemoteStateV3,
    UninterpretedGlossaryTerm,
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


def _remote_parent_id(properties: dict[str, Any]) -> str | None:
    if "parentId" not in properties:
        return None
    return properties["parentId"]


def _remote_acronyms(properties: dict[str, Any]) -> list[str]:
    if "acronyms" not in properties:
        return []
    return list(properties["acronyms"])


def _status_blocks_replace(remote: NormalizedGlossaryTerm) -> bool:
    status = remote.safety_properties.get("status")
    return status in {"PUBLISHED", "EXPIRED"}


def _acronym_change_reasons(
    desired: GlossaryTermDesiredState,
    remote: NormalizedGlossaryTerm,
) -> list[DiffReason]:
    if desired.acronyms is None:
        return []
    desired_acronyms = sorted(desired.acronyms)
    remote_acronyms = sorted(_remote_acronyms(remote.properties))
    if desired_acronyms != remote_acronyms:
        return [
            reason(
                "properties.acronyms.changed",
                "/properties/acronyms",
                before=canonical_json_scalar(remote_acronyms),
                after=canonical_json_scalar(desired_acronyms),
            )
        ]
    return []


def _property_change_reasons(
    desired: GlossaryTermDesiredState,
    remote: NormalizedGlossaryTerm,
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

    if desired.description != remote_props["description"]:
        reasons.append(
            reason(
                "properties.description.changed",
                "/properties/description",
                before=remote_props["description"],
                after=desired.description,
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

    reasons.extend(_acronym_change_reasons(desired, remote))
    return reasons


def _compare_matched(
    desired: GlossaryTermDesiredState,
    remote: NormalizedGlossaryTerm,
) -> DiffGlossaryTermItem:
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
            reasons.append(
                reason("plan.glossary_term_domain_move_unverified", "/properties/domain")
            )
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

    return DiffGlossaryTermItem(
        id=desired.id,
        resource_type="glossaryTerm",
        outcome=outcome,
        reasons=sorted_reasons,
    )


def _item_for_uninterpreted(
    item: UninterpretedGlossaryTerm,
    *,
    has_desired: bool,
) -> DiffGlossaryTermItem | None:
    if item.id is None:
        return None
    reasons: list[DiffReason] = [reason(item.reason_code, "/")]
    if not has_desired:
        reasons.append(reason("remote.absent_desired", "/"))
    return DiffGlossaryTermItem(
        id=item.id,
        resource_type="glossaryTerm",
        outcome="blocked",
        reasons=sort_reasons(reasons),
    )


def _item_remote_only(remote: NormalizedGlossaryTerm) -> DiffGlossaryTermItem:
    reasons = _unsupported_configurable_reasons(remote.unsupported_configurable_fields)
    reasons.append(reason("remote.absent_desired", "/"))
    return DiffGlossaryTermItem(
        id=remote.id,
        resource_type="glossaryTerm",
        outcome="remote-only",
        reasons=sort_reasons(reasons),
    )


def _item_create(desired: GlossaryTermDesiredState) -> DiffGlossaryTermItem:
    return DiffGlossaryTermItem(
        id=desired.id,
        resource_type="glossaryTerm",
        outcome="create",
        reasons=sort_reasons([reason("desired.absent_remote", "/")]),
    )


def _sort_key(item: DiffGlossaryTermItem) -> tuple[int, str]:
    return (2, item.id)


def diff_glossary_terms(
    desired: DesiredStateV3,
    remote: RemoteStateV3,
) -> tuple[DiffGlossaryTermItem, ...]:
    """Compare desired Glossary Terms against remote-state/v3 (UUID-only matching)."""
    remote_by_id: dict[str, NormalizedGlossaryTerm] = {
        item.id: item for item in remote.glossary_terms
    }
    uninterpreted_by_id: dict[str, UninterpretedGlossaryTerm] = {}
    for item in remote.uninterpreted_glossary_terms:
        if item.id is not None:
            uninterpreted_by_id[item.id] = item

    desired_ids = {item.id for item in desired.glossary_terms}
    items: list[DiffGlossaryTermItem] = []

    for term in desired.glossary_terms:
        if term.id in uninterpreted_by_id:
            item = _item_for_uninterpreted(
                uninterpreted_by_id[term.id],
                has_desired=True,
            )
            if item is not None:
                items.append(item)
            continue

        remote_term = remote_by_id.get(term.id)
        if remote_term is None:
            items.append(_item_create(term))
            continue

        items.append(_compare_matched(term, remote_term))

    for term_id, remote_term in remote_by_id.items():
        if term_id not in desired_ids:
            items.append(_item_remote_only(remote_term))

    for term_id, uninterpreted in uninterpreted_by_id.items():
        if term_id not in desired_ids:
            item = _item_for_uninterpreted(uninterpreted, has_desired=False)
            if item is not None:
                items.append(item)

    return tuple(sorted(items, key=_sort_key))
