"""Deterministic desired-vs-remote diff matrix."""

from __future__ import annotations

from purview_governance.desired.models import DataSourceDesiredState, DesiredState
from purview_governance.diff import diff_desired_vs_remote
from purview_governance.remote_state.models import (
    NormalizedDataSource,
    ObservedProperties,
    UninterpretedDataSource,
    UnknownLegacyMovingState,
    build_remote_state,
)


def _desired(
    name: str = "alphaSource",
    *,
    endpoint: str = "https://example.blob.core.windows.net/",
    collection: str = "Collection-rZX",
) -> DesiredState:
    return DesiredState(
        data_sources=(
            DataSourceDesiredState(
                name=name,
                kind="AzureStorage",
                endpoint=endpoint,
                collection_reference_name=collection,
            ),
        )
    )


def _remote(
    name: str = "alphaSource",
    *,
    creation_type: str = "Manual",
    moving: str | UnknownLegacyMovingState = "Active",
    endpoint: str = "https://example.blob.core.windows.net/",
    collection: str = "Collection-rZX",
) -> NormalizedDataSource:
    return NormalizedDataSource(
        name=name,
        kind="AzureStorage",
        creation_type=creation_type,  # type: ignore[arg-type]
        endpoint=endpoint,
        collection_reference_name=collection,
        collection_moving_state=moving,  # type: ignore[arg-type]
        observed=ObservedProperties(),
    )


def _outcomes(doc: object) -> dict[str, str]:
    return {item.name: item.outcome for item in doc.items}  # type: ignore[attr-defined]


def test_endpoint_only_replace() -> None:
    remote = build_remote_state((_remote(),), ())
    desired = _desired(endpoint="https://other.blob.core.windows.net/")
    doc = diff_desired_vs_remote(desired, remote)
    assert _outcomes(doc) == {"alphaSource": "replace"}
    assert doc.items[0].reasons[0].code == "properties.endpoint.changed"


def test_collection_only_and_combined_blocked() -> None:
    remote = build_remote_state((_remote(),), ())
    desired = _desired(collection="other-collection")
    doc = diff_desired_vs_remote(desired, remote)
    assert _outcomes(doc) == {"alphaSource": "blocked"}

    desired2 = _desired(
        endpoint="https://other.blob.core.windows.net/",
        collection="other-collection",
    )
    doc2 = diff_desired_vs_remote(desired2, remote)
    assert _outcomes(doc2) == {"alphaSource": "blocked"}
    codes = {r.code for r in doc2.items[0].reasons}
    assert "properties.endpoint.changed" in codes
    assert "properties.collection.referenceName.changed" in codes


def test_no_op_safe_equivalent() -> None:
    remote = build_remote_state((_remote(),), ())
    doc = diff_desired_vs_remote(_desired(), remote)
    assert _outcomes(doc) == {"alphaSource": "no-op"}


def test_create_and_remote_only() -> None:
    remote = build_remote_state((), ())
    doc = diff_desired_vs_remote(_desired(), remote)
    assert _outcomes(doc) == {"alphaSource": "create"}

    remote2 = build_remote_state((_remote(),), ())
    doc2 = diff_desired_vs_remote(DesiredState(data_sources=()), remote2)
    assert _outcomes(doc2) == {"alphaSource": "remote-only"}


def test_remote_only_preserves_outcome_with_safety_reasons() -> None:
    remote = build_remote_state(
        (_remote(creation_type="AutoManaged"),),
        (),
    )
    doc = diff_desired_vs_remote(DesiredState(data_sources=()), remote)
    assert _outcomes(doc) == {"alphaSource": "remote-only"}
    assert any(r.code == "remote.creation_type_auto_managed" for r in doc.items[0].reasons)

    remote2 = build_remote_state((_remote(moving="Moving"),), ())
    doc2 = diff_desired_vs_remote(DesiredState(data_sources=()), remote2)
    assert _outcomes(doc2) == {"alphaSource": "remote-only"}

    remote3 = build_remote_state(
        (_remote(moving=UnknownLegacyMovingState()),),
        (),
    )
    doc3 = diff_desired_vs_remote(DesiredState(data_sources=()), remote3)
    assert _outcomes(doc3) == {"alphaSource": "remote-only"}
    assert any(
        r.code == "remote.collection_moving_state_uninterpreted" for r in doc3.items[0].reasons
    )


def test_safety_blocks_when_desired_present() -> None:
    remote = build_remote_state((_remote(creation_type="AutoManaged"),), ())
    doc = diff_desired_vs_remote(_desired(), remote)
    assert _outcomes(doc) == {"alphaSource": "blocked"}

    remote2 = build_remote_state((_remote(moving="Moving"),), ())
    doc2 = diff_desired_vs_remote(_desired(), remote2)
    assert _outcomes(doc2) == {"alphaSource": "blocked"}

    remote3 = build_remote_state((_remote(moving="Failed"),), ())
    doc3 = diff_desired_vs_remote(_desired(), remote3)
    assert _outcomes(doc3) == {"alphaSource": "blocked"}

    remote4 = build_remote_state(
        (_remote(moving=UnknownLegacyMovingState()),),
        (),
    )
    doc4 = diff_desired_vs_remote(_desired(), remote4)
    assert _outcomes(doc4) == {"alphaSource": "blocked"}


def test_endpoint_plus_automanaged_blocked() -> None:
    remote = build_remote_state((_remote(creation_type="AutoManaged"),), ())
    desired = _desired(endpoint="https://other.blob.core.windows.net/")
    doc = diff_desired_vs_remote(desired, remote)
    assert _outcomes(doc) == {"alphaSource": "blocked"}


def test_unsupported_blocked_with_or_without_desired() -> None:
    remote = build_remote_state(
        (),
        (
            UninterpretedDataSource(
                name="otherSource",
                kind="AdlsGen2",
                reason_code="remote_state.unsupported_kind",
            ),
        ),
    )
    doc = diff_desired_vs_remote(DesiredState(data_sources=()), remote)
    assert _outcomes(doc) == {"otherSource": "blocked"}

    desired = DesiredState(
        data_sources=(
            DataSourceDesiredState(
                name="otherSource",
                kind="AzureStorage",
                endpoint="https://example.blob.core.windows.net/",
                collection_reference_name="root",
            ),
        )
    )
    doc2 = diff_desired_vs_remote(desired, remote)
    assert _outcomes(doc2) == {"otherSource": "blocked"}
