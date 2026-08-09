"""Unit tests for AzureStorage remote-state normalization policy."""

from __future__ import annotations

import pytest

from purview_governance.remote_state.errors import RemoteStateError
from purview_governance.remote_state.models import UnknownLegacyMovingState, build_remote_state
from purview_governance.remote_state.normalize import normalize_azure_storage_get
from tests.contract.server import azure_storage_fixture


def test_manual_active_normalizes() -> None:
    body = azure_storage_fixture("alphaSource")
    result = normalize_azure_storage_get(body, requested_name="alphaSource")
    assert result.creation_type == "Manual"
    assert result.collection_moving_state == "Active"
    assert result.endpoint == "https://example.blob.core.windows.net/"


def test_legacy_zero_is_uninterpreted_never_active() -> None:
    # Official Get example wire quirk — must not map "0" to Active.
    body = azure_storage_fixture("alphaSource", moving_state="0")
    result = normalize_azure_storage_get(body, requested_name="alphaSource")
    assert isinstance(result.collection_moving_state, UnknownLegacyMovingState)
    assert result.collection_moving_state.raw == "0"
    assert result.collection_moving_state != "Active"


def test_unknown_moving_state_fail_closed() -> None:
    body = azure_storage_fixture("alphaSource", moving_state="1")
    with pytest.raises(RemoteStateError) as exc:
        normalize_azure_storage_get(body, requested_name="alphaSource")
    assert exc.value.code == "remote_state.invalid_collection_moving_state"


def test_missing_creation_type_fail_closed() -> None:
    body = azure_storage_fixture("alphaSource")
    del body["creationType"]
    with pytest.raises(RemoteStateError) as exc:
        normalize_azure_storage_get(body, requested_name="alphaSource")
    assert exc.value.code == "remote_state.missing_creation_type"


def test_invalid_collection_type_fail_closed() -> None:
    body = azure_storage_fixture("alphaSource")
    body["properties"]["collection"]["type"] = "SomethingElse"
    with pytest.raises(RemoteStateError) as exc:
        normalize_azure_storage_get(body, requested_name="alphaSource")
    assert exc.value.code == "remote_state.invalid_collection_type"


def test_scans_absent_and_empty_equivalent() -> None:
    absent = normalize_azure_storage_get(
        azure_storage_fixture("alphaSource", omit_scans=True),
        requested_name="alphaSource",
    )
    empty = normalize_azure_storage_get(
        azure_storage_fixture("alphaSource", omit_scans=False, include_scans=[]),
        requested_name="alphaSource",
    )
    a = build_remote_state((absent,), ())
    b = build_remote_state((empty,), ())
    assert a.to_canonical_json() == b.to_canonical_json()
    assert a.material_state_identity == b.material_state_identity


def test_scans_nonempty_fail_closed_no_raw_in_error() -> None:
    marker = "embedded-scan-payload-must-not-leak"
    body = azure_storage_fixture(
        "alphaSource",
        omit_scans=False,
        include_scans=[{"name": "s1", "marker": marker}],
    )
    with pytest.raises(RemoteStateError) as exc:
        normalize_azure_storage_get(body, requested_name="alphaSource")
    assert exc.value.code == "remote_state.nested_scans_unsupported"
    assert marker not in str(exc.value)
    assert marker not in repr(exc.value)


def test_identity_mismatch_and_missing_name_kind() -> None:
    body = azure_storage_fixture("otherSource")
    with pytest.raises(RemoteStateError) as exc:
        normalize_azure_storage_get(body, requested_name="alphaSource")
    assert exc.value.code == "remote_state.identity_mismatch"

    missing_name = azure_storage_fixture("alphaSource")
    del missing_name["name"]
    with pytest.raises(RemoteStateError) as exc:
        normalize_azure_storage_get(missing_name, requested_name="alphaSource")
    assert exc.value.code == "remote_state.identity_mismatch"

    missing_kind = azure_storage_fixture("alphaSource")
    del missing_kind["kind"]
    with pytest.raises(RemoteStateError) as exc:
        normalize_azure_storage_get(missing_kind, requested_name="alphaSource")
    assert exc.value.code == "remote_state.missing_kind"


def test_sensitive_field_fail_closed() -> None:
    sentinel = "SUPER-SECRET-ACCOUNT-KEY-VALUE"
    body = azure_storage_fixture("alphaSource")
    body["properties"]["accountKey"] = sentinel
    with pytest.raises(RemoteStateError) as exc:
        normalize_azure_storage_get(body, requested_name="alphaSource")
    assert exc.value.code == "remote_state.sensitive_field"
    assert sentinel not in str(exc.value)
    assert sentinel not in repr(exc.value)
    assert not hasattr(exc.value, "body")


def test_unknown_field_fail_closed() -> None:
    body = azure_storage_fixture("alphaSource")
    body["unexpected"] = True
    with pytest.raises(RemoteStateError) as exc:
        normalize_azure_storage_get(body, requested_name="alphaSource")
    assert exc.value.code == "remote_state.unknown_field"


def test_hash_ignores_timestamps_and_tracks_safety() -> None:
    base = azure_storage_fixture("alphaSource")
    with_ts = azure_storage_fixture("alphaSource", include_timestamps=True)
    a = build_remote_state(
        (normalize_azure_storage_get(base, requested_name="alphaSource"),),
        (),
    )
    b = build_remote_state(
        (normalize_azure_storage_get(with_ts, requested_name="alphaSource"),),
        (),
    )
    assert a.material_state_identity == b.material_state_identity

    auto = azure_storage_fixture("alphaSource", creation_type="AutoManaged")
    c = build_remote_state(
        (normalize_azure_storage_get(auto, requested_name="alphaSource"),),
        (),
    )
    assert c.material_state_identity != a.material_state_identity

    moving = azure_storage_fixture("alphaSource", moving_state="Moving")
    d = build_remote_state(
        (normalize_azure_storage_get(moving, requested_name="alphaSource"),),
        (),
    )
    assert d.material_state_identity != a.material_state_identity

    legacy = azure_storage_fixture("alphaSource", moving_state="0")
    e = build_remote_state(
        (normalize_azure_storage_get(legacy, requested_name="alphaSource"),),
        (),
    )
    assert e.material_state_identity != a.material_state_identity

    observed = azure_storage_fixture(
        "alphaSource",
        observed={"resourceGroup": "rg-a"},
    )
    f = build_remote_state(
        (normalize_azure_storage_get(observed, requested_name="alphaSource"),),
        (),
    )
    assert f.material_state_identity != a.material_state_identity
