"""Regression tests for desired-after binding and reason provenance."""

from __future__ import annotations

import json

import pytest

from purview_governance.config.models import (
    AuthenticationConfig,
    DataSourceResourceConfig,
    GovernanceConfig,
    TargetConfig,
)
from purview_governance.plan import (
    PlanBuildError,
    PlanIntegrityError,
    build_governance_plan,
    load_plan_text,
)
from purview_governance.remote_state.canonical import compute_material_state_identity
from purview_governance.remote_state.models import (
    RemoteState,
    UninterpretedDataSource,
    build_remote_state,
)
from tests.plan.helpers import (
    create_config,
    empty_config,
    recompute_plan_identity,
    remote_ds,
)


def test_replace_after_must_equal_desired_endpoint() -> None:
    remote = build_remote_state(
        (remote_ds(endpoint="https://old.blob.core.windows.net/"),),
        (),
    )
    document = build_governance_plan(create_config(), remote).to_document()
    document["changeSet"]["items"][0]["reasons"][0]["after"] = (
        "https://different-but-safe.blob.core.windows.net/"
    )
    document = recompute_plan_identity(document)
    with pytest.raises(PlanIntegrityError) as exc_info:
        load_plan_text(json.dumps(document))
    assert exc_info.value.code == "plan.invalid_reason_outcome"


def test_blocked_endpoint_after_must_equal_desired() -> None:
    remote = build_remote_state(
        (
            remote_ds(
                creation_type="AutoNative",
                endpoint="https://old.blob.core.windows.net/",
            ),
        ),
        (),
    )
    document = build_governance_plan(create_config(), remote).to_document()
    for reason in document["changeSet"]["items"][0]["reasons"]:
        if reason["code"] == "properties.endpoint.changed":
            reason["after"] = "https://different-but-safe.blob.core.windows.net/"
    document = recompute_plan_identity(document)
    with pytest.raises(PlanIntegrityError) as exc_info:
        load_plan_text(json.dumps(document))
    assert exc_info.value.code == "plan.invalid_reason_outcome"


def test_blocked_collection_after_must_equal_desired() -> None:
    config = GovernanceConfig(
        api_version="purview-governance-config/v1",
        target=TargetConfig(endpoint="https://account.purview.azure.com"),
        authentication=AuthenticationConfig(strategy="defaultAzureCredential"),
        resources=(
            DataSourceResourceConfig(
                name="example-source",
                kind="AzureStorage",
                endpoint="https://example.blob.core.windows.net/",
                collection_reference_name="desired-collection",
            ),
        ),
    )
    remote = build_remote_state((remote_ds(collection="root"),), ())
    document = build_governance_plan(config, remote).to_document()
    for reason in document["changeSet"]["items"][0]["reasons"]:
        if reason["code"] == "properties.collection.referenceName.changed":
            reason["after"] = "other-collection"
    document = recompute_plan_identity(document)
    with pytest.raises(PlanIntegrityError) as exc_info:
        load_plan_text(json.dumps(document))
    assert exc_info.value.code == "plan.invalid_reason_outcome"


def test_valid_replace_and_blocked_after_binding_accepted() -> None:
    remote = build_remote_state(
        (remote_ds(endpoint="https://old.blob.core.windows.net/"),),
        (),
    )
    plan = build_governance_plan(create_config(), remote)
    loaded = load_plan_text(plan.to_canonical_json())
    assert loaded.plan_identity == plan.plan_identity
    assert loaded.change_set.items[0].reasons[0].after == (
        loaded.desired_state.data_sources[0].endpoint
    )

    blocked_remote = build_remote_state(
        (
            remote_ds(
                creation_type="AutoNative",
                endpoint="https://old.blob.core.windows.net/",
                collection="other",
            ),
        ),
        (),
    )
    blocked = build_governance_plan(create_config(), blocked_remote)
    loaded_blocked = load_plan_text(blocked.to_canonical_json())
    desired = loaded_blocked.desired_state.data_sources[0]
    for reason in loaded_blocked.change_set.items[0].reasons:
        if reason.code == "properties.endpoint.changed":
            assert reason.after == desired.endpoint
        if reason.code == "properties.collection.referenceName.changed":
            assert reason.after == desired.collection_reference_name


def test_uninterpreted_azurestorage_kind_rejected_by_builder() -> None:
    item = UninterpretedDataSource(
        name="x-source",
        kind="AzureStorage",
        reason_code="remote_state.unsupported_kind",
    )
    provisional = RemoteState((), (item,), "")
    identity = compute_material_state_identity(provisional.identity_document())
    remote = RemoteState((), (item,), identity)
    with pytest.raises(PlanBuildError) as exc_info:
        build_governance_plan(empty_config(), remote)
    assert exc_info.value.code == "plan.invalid_remote_state_input"


def test_unsupported_before_azurestorage_rejected() -> None:
    remote = build_remote_state(
        (),
        (
            UninterpretedDataSource(
                name="weird-source",
                kind="AdlsGen2",
                reason_code="remote_state.unsupported_kind",
            ),
        ),
    )
    document = build_governance_plan(empty_config(), remote).to_document()
    for reason in document["changeSet"]["items"][0]["reasons"]:
        if reason["code"] == "remote_state.unsupported_kind":
            reason["before"] = "AzureStorage"
    document = recompute_plan_identity(document)
    with pytest.raises(PlanIntegrityError) as exc_info:
        load_plan_text(json.dumps(document))
    assert exc_info.value.code == "plan.invalid_reason"


def test_unsupported_with_desired_mismatched_before_rejected() -> None:
    remote = build_remote_state(
        (),
        (
            UninterpretedDataSource(
                name="example-source",
                kind="AdlsGen2",
                reason_code="remote_state.unsupported_kind",
            ),
        ),
    )
    document = build_governance_plan(create_config(), remote).to_document()
    for reason in document["changeSet"]["items"][0]["reasons"]:
        if reason["code"] == "kind.changed":
            reason["before"] = "OtherKind"
    document = recompute_plan_identity(document)
    with pytest.raises(PlanIntegrityError) as exc_info:
        load_plan_text(json.dumps(document))
    assert exc_info.value.code == "plan.invalid_reason_outcome"


def test_legitimate_unsupported_pair_accepted() -> None:
    remote = build_remote_state(
        (),
        (
            UninterpretedDataSource(
                name="example-source",
                kind="AdlsGen2",
                reason_code="remote_state.unsupported_kind",
            ),
        ),
    )
    plan = build_governance_plan(create_config(), remote)
    loaded = load_plan_text(plan.to_canonical_json())
    reasons = {r.code: r for r in loaded.change_set.items[0].reasons}
    assert reasons["remote_state.unsupported_kind"].before == reasons["kind.changed"].before
    assert reasons["kind.changed"].after == "AzureStorage"
    assert reasons["remote_state.unsupported_kind"].before != "AzureStorage"


def test_mutually_exclusive_creation_and_moving_groups() -> None:
    remote = build_remote_state((remote_ds(name="unmanaged", creation_type="AutoNative"),), ())
    document = build_governance_plan(empty_config(), remote).to_document()
    document["changeSet"]["items"][0]["reasons"] = [
        {"code": "remote.absent_desired", "path": "/"},
        {
            "code": "remote.creation_type_auto_managed",
            "path": "/creationType",
            "before": "AutoManaged",
        },
        {
            "code": "remote.creation_type_auto_native",
            "path": "/creationType",
            "before": "AutoNative",
        },
    ]
    document["changeSet"]["items"][0]["reasons"].sort(key=lambda r: (r["path"], r["code"]))
    document = recompute_plan_identity(document)
    with pytest.raises(PlanIntegrityError) as exc_info:
        load_plan_text(json.dumps(document))
    assert exc_info.value.code == "plan.invalid_reason_outcome"

    document2 = build_governance_plan(empty_config(), remote).to_document()
    document2["changeSet"]["items"][0]["reasons"] = [
        {"code": "remote.absent_desired", "path": "/"},
        {
            "code": "remote.collection_move_failed",
            "path": "/properties/dataSourceCollectionMovingState",
            "before": "Failed",
        },
        {
            "code": "remote.collection_moving",
            "path": "/properties/dataSourceCollectionMovingState",
            "before": "Moving",
        },
    ]
    document2["changeSet"]["items"][0]["reasons"].sort(key=lambda r: (r["path"], r["code"]))
    document2 = recompute_plan_identity(document2)
    with pytest.raises(PlanIntegrityError) as exc_info:
        load_plan_text(json.dumps(document2))
    assert exc_info.value.code == "plan.invalid_reason_outcome"


def test_supported_blocked_rejects_kind_changed() -> None:
    remote = build_remote_state((remote_ds(creation_type="AutoNative"),), ())
    document = build_governance_plan(create_config(), remote).to_document()
    document["changeSet"]["items"][0]["reasons"].append(
        {
            "code": "kind.changed",
            "path": "/kind",
            "before": "AdlsGen2",
            "after": "AzureStorage",
        }
    )
    document["changeSet"]["items"][0]["reasons"].sort(key=lambda r: (r["path"], r["code"]))
    document = recompute_plan_identity(document)
    with pytest.raises(PlanIntegrityError) as exc_info:
        load_plan_text(json.dumps(document))
    assert exc_info.value.code == "plan.invalid_reason_outcome"

    document2 = build_governance_plan(create_config(), remote).to_document()
    document2["changeSet"]["items"][0]["reasons"] = [
        {
            "code": "kind.changed",
            "path": "/kind",
            "before": "AdlsGen2",
            "after": "AzureStorage",
        }
    ]
    document2 = recompute_plan_identity(document2)
    with pytest.raises(PlanIntegrityError) as exc_info:
        load_plan_text(json.dumps(document2))
    assert exc_info.value.code == "plan.invalid_reason_outcome"


def test_valid_autonative_plus_moving_accepted() -> None:
    remote = build_remote_state(
        (remote_ds(name="unmanaged", creation_type="AutoNative", moving="Moving"),),
        (),
    )
    plan = build_governance_plan(empty_config(), remote)
    loaded = load_plan_text(plan.to_canonical_json())
    codes = [r.code for r in loaded.change_set.items[0].reasons]
    assert codes.count("remote.creation_type_auto_native") == 1
    assert codes.count("remote.collection_moving") == 1
