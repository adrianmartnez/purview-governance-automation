"""Offline API contract tests for read-only remote-state capture."""

from __future__ import annotations

import pytest

from purview_governance.remote_state import capture_remote_state
from purview_governance.remote_state.errors import RemoteStateError
from purview_governance.remote_state.models import UnknownLegacyMovingState
from tests.contract.client_helpers import make_loopback_client
from tests.contract.server import azure_storage_fixture, start_contract_server


def _data_plane_recordings(server: object) -> list[object]:
    return [
        rec
        for rec in server.state.recordings  # type: ignore[attr-defined]
        if rec.path != "/health"
    ]


@pytest.mark.api_contract
def test_capture_empty_list_get_only() -> None:
    with start_contract_server(list_mode="empty") as server:
        with make_loopback_client(server.base_url) as client:
            state = capture_remote_state(client)
        assert state.data_sources == ()
        assert state.uninterpreted_data_sources == ()
        recs = _data_plane_recordings(server)
        assert all(rec.method == "GET" for rec in recs)
        assert not any(rec.method == "PUT" for rec in server.state.recordings)


@pytest.mark.api_contract
def test_capture_multi_unordered_canonical_order() -> None:
    bodies = {
        "alphaSource": azure_storage_fixture("alphaSource"),
        "zetaSource": azure_storage_fixture("zetaSource"),
    }
    with start_contract_server(list_mode="multi_unordered", get_bodies=bodies) as server:
        with make_loopback_client(server.base_url) as client:
            state = capture_remote_state(client)
        assert [ds.name for ds in state.data_sources] == ["alphaSource", "zetaSource"]
        recs = _data_plane_recordings(server)
        assert all(rec.method == "GET" for rec in recs)
        assert not any(rec.method == "PUT" for rec in server.state.recordings)


@pytest.mark.api_contract
def test_capture_legacy_zero_and_unsupported_mix() -> None:
    bodies = {
        "alphaSource": azure_storage_fixture("alphaSource", moving_state="0"),
        "betaSource": {
            "name": "betaSource",
            "kind": "AdlsGen2",
            "creationType": "Manual",
            "properties": {
                "endpoint": "https://datalake.dfs.core.windows.net/",
                "collection": {"referenceName": "root"},
                "dataSourceCollectionMovingState": "Active",
            },
        },
    }
    with start_contract_server(list_mode="remote_state_mix", get_bodies=bodies) as server:
        with make_loopback_client(server.base_url) as client:
            state = capture_remote_state(client)
        assert len(state.data_sources) == 1
        assert isinstance(
            state.data_sources[0].collection_moving_state,
            UnknownLegacyMovingState,
        )
        assert state.uninterpreted_data_sources[0].name == "betaSource"
        assert not any(rec.method == "PUT" for rec in server.state.recordings)


@pytest.mark.api_contract
def test_capture_unknown_field_fail_closed() -> None:
    with (
        start_contract_server(list_mode="one_page", get_mode="unknown_field") as server,
        make_loopback_client(server.base_url) as client,
        pytest.raises(RemoteStateError) as exc,
    ):
        capture_remote_state(client)
    assert exc.value.code == "remote_state.unknown_field"
    assert not any(rec.method == "PUT" for rec in server.state.recordings)


@pytest.mark.api_contract
def test_capture_scans_nonempty_fail_closed() -> None:
    with (
        start_contract_server(list_mode="one_page", get_mode="scans_nonempty") as server,
        make_loopback_client(server.base_url) as client,
        pytest.raises(RemoteStateError) as exc,
    ):
        capture_remote_state(client)
    assert exc.value.code == "remote_state.nested_scans_unsupported"


@pytest.mark.api_contract
def test_capture_identity_mismatch_fail_closed() -> None:
    with (
        start_contract_server(list_mode="one_page", get_mode="identity_mismatch") as server,
        make_loopback_client(server.base_url) as client,
        pytest.raises(RemoteStateError) as exc,
    ):
        capture_remote_state(client)
    assert exc.value.code == "remote_state.identity_mismatch"
