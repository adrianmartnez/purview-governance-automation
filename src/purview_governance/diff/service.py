"""Read-only deterministic desired-vs-remote multi-resource diff."""

from __future__ import annotations

from purview_governance.desired.models import (
    DataSourceDesiredState,
    DesiredState,
    ScanDesiredState,
    ScanRuleSetDesiredState,
)
from purview_governance.diff.models import DiffDocument, DiffItem, DiffOutcome, DiffReason
from purview_governance.diff.reasons import reason, sort_reasons
from purview_governance.remote_state.canonical import canonical_json_scalar, dumps_canonical
from purview_governance.remote_state.models import (
    NormalizedDataSource,
    NormalizedScan,
    NormalizedScanRuleSet,
    RemoteState,
    RemoteStateV2,
    UninterpretedDataSource,
    UninterpretedScan,
    UninterpretedScanRuleSet,
    UnknownLegacyMovingState,
    UnsupportedConfigurableField,
)

_TYPE_RANK: dict[str, int] = {"dataSource": 0, "scanRuleSet": 1, "scan": 2}


def _sort_items(items: list[DiffItem]) -> tuple[DiffItem, ...]:
    return tuple(
        sorted(
            items,
            key=lambda item: (
                _TYPE_RANK[item.resource_type],
                item.data_source_name or "",
                item.name,
            ),
        )
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


def _compare_data_source(
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


def _item_for_uninterpreted_data_source(
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


def _item_remote_only_data_source(remote: NormalizedDataSource) -> DiffItem:
    reasons = _ownership_safety_reasons(remote)
    reasons.append(reason("remote.absent_desired", "/"))
    return DiffItem(
        name=remote.name,
        resource_type="dataSource",
        outcome="remote-only",
        reasons=sort_reasons(reasons),
    )


def _item_create_data_source(desired: DataSourceDesiredState) -> DiffItem:
    return DiffItem(
        name=desired.name,
        resource_type="dataSource",
        outcome="create",
        reasons=sort_reasons([reason("desired.absent_remote", "/")]),
    )


def _diff_data_sources(
    desired: DesiredState,
    *,
    data_sources: tuple[NormalizedDataSource, ...],
    uninterpreted_data_sources: tuple[UninterpretedDataSource, ...],
) -> list[DiffItem]:
    desired_by_name = {item.name: item for item in desired.data_sources}
    remote_by_name = {item.name: item for item in data_sources}
    uninterpreted_by_name = {item.name: item for item in uninterpreted_data_sources}

    names = sorted(set(desired_by_name) | set(remote_by_name) | set(uninterpreted_by_name))
    items: list[DiffItem] = []
    for name in names:
        if name in uninterpreted_by_name:
            items.append(
                _item_for_uninterpreted_data_source(
                    uninterpreted_by_name[name],
                    has_desired=name in desired_by_name,
                )
            )
            continue
        has_desired = name in desired_by_name
        has_remote = name in remote_by_name
        if has_remote and not has_desired:
            items.append(_item_remote_only_data_source(remote_by_name[name]))
            continue
        if has_desired and not has_remote:
            items.append(_item_create_data_source(desired_by_name[name]))
            continue
        items.append(_compare_data_source(desired_by_name[name], remote_by_name[name]))
    return items


def _scan_creation_ownership_reasons(remote: NormalizedScan) -> list[DiffReason]:
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
    return reasons


def _scan_creation_ownership_blocks(remote: NormalizedScan) -> bool:
    return remote.creation_type in {"AutoNative", "AutoManaged"}


def _unsupported_configurable_reasons(
    fields: tuple[UnsupportedConfigurableField, ...],
) -> list[DiffReason]:
    return [
        reason("remote.unsupported_configurable_field", field.path)
        for field in sorted(fields, key=lambda item: item.path)
    ]


def _compare_scan(desired: ScanDesiredState, remote: NormalizedScan) -> DiffItem:
    reasons: list[DiffReason] = []
    blocking = False

    if remote.unsupported_configurable_fields:
        blocking = True
        reasons.extend(_unsupported_configurable_reasons(remote.unsupported_configurable_fields))

    if _scan_creation_ownership_blocks(remote):
        blocking = True
        reasons.extend(_scan_creation_ownership_reasons(remote))

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

    ruleset_name_changed = desired.scan_ruleset_name != remote.scan_ruleset_name
    if ruleset_name_changed:
        reasons.append(
            reason(
                "properties.scanRulesetName.changed",
                "/properties/scanRulesetName",
                before=remote.scan_ruleset_name,
                after=desired.scan_ruleset_name,
            )
        )

    ruleset_type_changed = desired.scan_ruleset_type != remote.scan_ruleset_type
    if ruleset_type_changed:
        reasons.append(
            reason(
                "properties.scanRulesetType.changed",
                "/properties/scanRulesetType",
                before=remote.scan_ruleset_type,
                after=desired.scan_ruleset_type,
            )
        )

    sorted_reasons = sort_reasons(reasons)
    if blocking:
        outcome: DiffOutcome = "blocked"
    elif ruleset_name_changed or ruleset_type_changed:
        outcome = "replace"
    else:
        outcome = "no-op"

    return DiffItem(
        name=desired.name,
        resource_type="scan",
        outcome=outcome,
        reasons=sorted_reasons,
        data_source_name=desired.data_source_name,
    )


def _item_for_uninterpreted_scan(
    item: UninterpretedScan,
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
        reasons.append(reason("kind.changed", "/kind", before=item.kind, after="AzureStorageMsi"))
    else:
        reasons.append(reason("remote.absent_desired", "/"))
    return DiffItem(
        name=item.name,
        resource_type="scan",
        outcome="blocked",
        reasons=sort_reasons(reasons),
        data_source_name=item.data_source_name,
    )


def _item_remote_only_scan(remote: NormalizedScan) -> DiffItem:
    reasons = _unsupported_configurable_reasons(remote.unsupported_configurable_fields)
    reasons.extend(_scan_creation_ownership_reasons(remote))
    reasons.append(reason("remote.absent_desired", "/"))
    return DiffItem(
        name=remote.name,
        resource_type="scan",
        outcome="remote-only",
        reasons=sort_reasons(reasons),
        data_source_name=remote.data_source_name,
    )


def _item_create_scan(desired: ScanDesiredState) -> DiffItem:
    return DiffItem(
        name=desired.name,
        resource_type="scan",
        outcome="create",
        reasons=sort_reasons([reason("desired.absent_remote", "/")]),
        data_source_name=desired.data_source_name,
    )


def _scan_key(data_source_name: str, name: str) -> tuple[str, str]:
    return (data_source_name, name)


def _diff_scans(
    desired: DesiredState,
    *,
    scans: tuple[NormalizedScan, ...],
    uninterpreted_scans: tuple[UninterpretedScan, ...],
) -> list[DiffItem]:
    desired_by_key = {_scan_key(item.data_source_name, item.name): item for item in desired.scans}
    remote_by_key = {_scan_key(item.data_source_name, item.name): item for item in scans}
    uninterpreted_by_key = {
        _scan_key(item.data_source_name, item.name): item for item in uninterpreted_scans
    }

    keys = sorted(set(desired_by_key) | set(remote_by_key) | set(uninterpreted_by_key))
    items: list[DiffItem] = []
    for key in keys:
        if key in uninterpreted_by_key:
            items.append(
                _item_for_uninterpreted_scan(
                    uninterpreted_by_key[key],
                    has_desired=key in desired_by_key,
                )
            )
            continue
        has_desired = key in desired_by_key
        has_remote = key in remote_by_key
        if has_remote and not has_desired:
            items.append(_item_remote_only_scan(remote_by_key[key]))
            continue
        if has_desired and not has_remote:
            items.append(_item_create_scan(desired_by_key[key]))
            continue
        items.append(_compare_scan(desired_by_key[key], remote_by_key[key]))
    return items


def _canonical_string_list(values: tuple[str, ...]) -> str:
    return dumps_canonical(list(values))


def _compare_scan_rule_set(
    desired: ScanRuleSetDesiredState,
    remote: NormalizedScanRuleSet,
) -> DiffItem:
    reasons: list[DiffReason] = []
    blocking = False

    if remote.unsupported_configurable_fields:
        blocking = True
        reasons.extend(_unsupported_configurable_reasons(remote.unsupported_configurable_fields))

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

    if desired.scan_ruleset_type != remote.scan_ruleset_type:
        reasons.append(
            reason(
                "scanRulesetType.changed",
                "/scanRulesetType",
                before=remote.scan_ruleset_type,
                after=desired.scan_ruleset_type,
            )
        )

    if desired.file_extensions != remote.file_extensions:
        reasons.append(
            reason(
                "properties.scanningRule.fileExtensions.changed",
                "/properties/scanningRule/fileExtensions",
                before=_canonical_string_list(remote.file_extensions),
                after=_canonical_string_list(desired.file_extensions),
            )
        )

    if desired.excluded_system_classifications != remote.excluded_system_classifications:
        reasons.append(
            reason(
                "properties.excludedSystemClassifications.changed",
                "/properties/excludedSystemClassifications",
                before=_canonical_string_list(remote.excluded_system_classifications),
                after=_canonical_string_list(desired.excluded_system_classifications),
            )
        )

    if (
        desired.included_custom_classification_rule_names
        != remote.included_custom_classification_rule_names
    ):
        reasons.append(
            reason(
                "properties.includedCustomClassificationRuleNames.changed",
                "/properties/includedCustomClassificationRuleNames",
                before=_canonical_string_list(remote.included_custom_classification_rule_names),
                after=_canonical_string_list(desired.included_custom_classification_rule_names),
            )
        )

    # Compare Python values; encode before/after with unambiguous JSON scalars
    # so None (null) and "" (JSON empty string) remain distinct in plan reasons.
    if desired.description != remote.description:
        reasons.append(
            reason(
                "properties.description.changed",
                "/properties/description",
                before=canonical_json_scalar(remote.description),
                after=canonical_json_scalar(desired.description),
            )
        )

    sorted_reasons = sort_reasons(reasons)
    material_changed = any(
        code
        in {
            "scanRulesetType.changed",
            "properties.scanningRule.fileExtensions.changed",
            "properties.excludedSystemClassifications.changed",
            "properties.includedCustomClassificationRuleNames.changed",
            "properties.description.changed",
        }
        for code in (item.code for item in sorted_reasons)
    )
    if blocking:
        outcome: DiffOutcome = "blocked"
    elif material_changed:
        outcome = "replace"
    else:
        outcome = "no-op"

    return DiffItem(
        name=desired.name,
        resource_type="scanRuleSet",
        outcome=outcome,
        reasons=sorted_reasons,
    )


def _item_for_uninterpreted_scan_rule_set(
    item: UninterpretedScanRuleSet,
    *,
    has_desired: bool,
) -> DiffItem:
    if item.reason_code == "remote_state.unsupported_scan_ruleset_type":
        # Exact non-Custom wire type is not retained on UninterpretedScanRuleSet.
        reasons = [
            reason(
                item.reason_code,
                "/scanRulesetType",
                before="System",
            )
        ]
        if has_desired:
            reasons.append(
                reason(
                    "scanRulesetType.changed",
                    "/scanRulesetType",
                    before="System",
                    after="Custom",
                )
            )
        else:
            reasons.append(reason("remote.absent_desired", "/"))
    else:
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
        resource_type="scanRuleSet",
        outcome="blocked",
        reasons=sort_reasons(reasons),
    )


def _item_remote_only_scan_rule_set(remote: NormalizedScanRuleSet) -> DiffItem:
    reasons = _unsupported_configurable_reasons(remote.unsupported_configurable_fields)
    reasons.append(reason("remote.absent_desired", "/"))
    return DiffItem(
        name=remote.name,
        resource_type="scanRuleSet",
        outcome="remote-only",
        reasons=sort_reasons(reasons),
    )


def _item_create_scan_rule_set(desired: ScanRuleSetDesiredState) -> DiffItem:
    return DiffItem(
        name=desired.name,
        resource_type="scanRuleSet",
        outcome="create",
        reasons=sort_reasons([reason("desired.absent_remote", "/")]),
    )


def _diff_scan_rule_sets(
    desired: DesiredState,
    *,
    scan_rule_sets: tuple[NormalizedScanRuleSet, ...],
    uninterpreted_scan_rule_sets: tuple[UninterpretedScanRuleSet, ...],
) -> list[DiffItem]:
    desired_by_name = {item.name: item for item in desired.scan_rule_sets}
    remote_by_name = {item.name: item for item in scan_rule_sets}
    uninterpreted_by_name = {item.name: item for item in uninterpreted_scan_rule_sets}

    names = sorted(set(desired_by_name) | set(remote_by_name) | set(uninterpreted_by_name))
    items: list[DiffItem] = []
    for name in names:
        if name in uninterpreted_by_name:
            items.append(
                _item_for_uninterpreted_scan_rule_set(
                    uninterpreted_by_name[name],
                    has_desired=name in desired_by_name,
                )
            )
            continue
        has_desired = name in desired_by_name
        has_remote = name in remote_by_name
        if has_remote and not has_desired:
            items.append(_item_remote_only_scan_rule_set(remote_by_name[name]))
            continue
        if has_desired and not has_remote:
            items.append(_item_create_scan_rule_set(desired_by_name[name]))
            continue
        items.append(_compare_scan_rule_set(desired_by_name[name], remote_by_name[name]))
    return items


def diff_desired_vs_remote(
    desired: DesiredState,
    remote: RemoteState | RemoteStateV2,
) -> DiffDocument:
    """Compare desired state to purview-remote-state/v1 or /v2 (pure / offline).

    Precedence:
    1. uninterpreted/unsupported kind -> blocked
    2. supported remote without desired -> remote-only
    3. desired without remote -> create
    4. both -> blocked / replace / no-op per ownership, safety, and material fields
    """
    items = _diff_data_sources(
        desired,
        data_sources=remote.data_sources,
        uninterpreted_data_sources=remote.uninterpreted_data_sources,
    )
    if isinstance(remote, RemoteStateV2):
        items.extend(
            _diff_scan_rule_sets(
                desired,
                scan_rule_sets=remote.scan_rule_sets,
                uninterpreted_scan_rule_sets=remote.uninterpreted_scan_rule_sets,
            )
        )
        items.extend(
            _diff_scans(
                desired,
                scans=remote.scans,
                uninterpreted_scans=remote.uninterpreted_scans,
            )
        )
    return DiffDocument(items=_sort_items(items))


def diff_desired_vs_remote_v2(desired: DesiredState, remote: RemoteStateV2) -> DiffDocument:
    """Compare desired state to purview-remote-state/v2 (DS + scans + SRS)."""
    return diff_desired_vs_remote(desired, remote)
