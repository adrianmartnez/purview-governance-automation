"""Read-only deterministic desired-vs-remote Data Source diff."""

from __future__ import annotations

from purview_governance.desired.models import DataSourceDesiredState, DesiredState
from purview_governance.diff.models import DiffDocument, DiffItem, DiffOutcome, DiffReason
from purview_governance.diff.reasons import reason, sort_reasons
from purview_governance.remote_state.models import (
    NormalizedDataSource,
    RemoteState,
    UninterpretedDataSource,
    UnknownLegacyMovingState,
)


def _ownership_safety_reasons(remote: NormalizedDataSource) -> list[DiffReason]:
    reasons: list[DiffReason] = []
    if remote.creation_type == "AutoNative":
        reasons.append(
            reason(
                "remote.creation_type_auto_native",
                "/creationType",
                before=remote.creation_type,
            )
        )
    elif remote.creation_type == "AutoManaged":
        reasons.append(
            reason(
                "remote.creation_type_auto_managed",
                "/creationType",
                before=remote.creation_type,
            )
        )

    moving = remote.collection_moving_state
    if isinstance(moving, UnknownLegacyMovingState):
        reasons.append(
            reason(
                "remote.collection_moving_state_uninterpreted",
                "/properties/dataSourceCollectionMovingState",
                before=moving.raw,
            )
        )
    elif moving == "Moving":
        reasons.append(
            reason(
                "remote.collection_moving",
                "/properties/dataSourceCollectionMovingState",
                before=moving,
            )
        )
    elif moving == "Failed":
        reasons.append(
            reason(
                "remote.collection_move_failed",
                "/properties/dataSourceCollectionMovingState",
                before=moving,
            )
        )
    return reasons


def _ownership_safety_blocks(remote: NormalizedDataSource) -> bool:
    if remote.creation_type in {"AutoNative", "AutoManaged"}:
        return True
    moving = remote.collection_moving_state
    if isinstance(moving, UnknownLegacyMovingState):
        return True
    return moving in {"Moving", "Failed"}


def _compare_both(
    desired: DataSourceDesiredState,
    remote: NormalizedDataSource,
) -> DiffItem:
    reasons: list[DiffReason] = []
    blocking = False

    if _ownership_safety_blocks(remote):
        blocking = True
        reasons.extend(_ownership_safety_reasons(remote))

    if desired.kind != remote.kind:
        blocking = True
        reasons.append(
            reason(
                "kind.changed",
                "/kind",
                before=remote.kind,
                after=desired.kind,
            )
        )

    if desired.collection_reference_name != remote.collection_reference_name:
        blocking = True
        reasons.append(
            reason(
                "properties.collection.referenceName.changed",
                "/properties/collection/referenceName",
                before=remote.collection_reference_name,
                after=desired.collection_reference_name,
            )
        )

    endpoint_changed = desired.endpoint != remote.endpoint
    if endpoint_changed:
        reasons.append(
            reason(
                "properties.endpoint.changed",
                "/properties/endpoint",
                before=remote.endpoint,
                after=desired.endpoint,
            )
        )

    sorted_reasons = sort_reasons(reasons)
    if blocking:
        outcome: DiffOutcome = "blocked"
    elif endpoint_changed:
        outcome = "replace"
    else:
        outcome = "no-op"

    return DiffItem(
        name=desired.name,
        resource_type="dataSource",
        outcome=outcome,
        reasons=sorted_reasons,
    )


def _item_for_uninterpreted(
    item: UninterpretedDataSource,
    *,
    has_desired: bool,
) -> DiffItem:
    reasons = [
        reason(
            item.reason_code,
            "/kind",
            before=item.kind,
        )
    ]
    if has_desired:
        reasons.append(reason("kind.changed", "/kind", before=item.kind, after="AzureStorage"))
    else:
        reasons.append(reason("remote.absent_desired", "/"))
    return DiffItem(
        name=item.name,
        resource_type="dataSource",
        outcome="blocked",
        reasons=sort_reasons(reasons),
    )


def _item_remote_only(remote: NormalizedDataSource) -> DiffItem:
    reasons = _ownership_safety_reasons(remote)
    reasons.append(reason("remote.absent_desired", "/"))
    return DiffItem(
        name=remote.name,
        resource_type="dataSource",
        outcome="remote-only",
        reasons=sort_reasons(reasons),
    )


def _item_create(desired: DataSourceDesiredState) -> DiffItem:
    return DiffItem(
        name=desired.name,
        resource_type="dataSource",
        outcome="create",
        reasons=sort_reasons([reason("desired.absent_remote", "/")]),
    )


def diff_desired_vs_remote(
    desired: DesiredState,
    remote: RemoteState,
) -> DiffDocument:
    """Compare desired state to purview-remote-state/v1 (pure / offline).

    Precedence:
    1. uninterpreted/unsupported kind -> blocked
    2. supported remote without desired -> remote-only
    3. desired without remote -> create
    4. both -> blocked / replace / no-op per ownership, safety, and material fields
    """
    desired_by_name = {item.name: item for item in desired.data_sources}
    remote_by_name = {item.name: item for item in remote.data_sources}
    uninterpreted_by_name = {item.name: item for item in remote.uninterpreted_data_sources}

    names = sorted(set(desired_by_name) | set(remote_by_name) | set(uninterpreted_by_name))
    items: list[DiffItem] = []
    for name in names:
        if name in uninterpreted_by_name:
            items.append(
                _item_for_uninterpreted(
                    uninterpreted_by_name[name],
                    has_desired=name in desired_by_name,
                )
            )
            continue
        has_desired = name in desired_by_name
        has_remote = name in remote_by_name
        if has_remote and not has_desired:
            items.append(_item_remote_only(remote_by_name[name]))
            continue
        if has_desired and not has_remote:
            items.append(_item_create(desired_by_name[name]))
            continue
        items.append(_compare_both(desired_by_name[name], remote_by_name[name]))

    return DiffDocument(items=tuple(items))
