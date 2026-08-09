"""Unit tests for read-only remote-state capture service."""

from __future__ import annotations

import pytest

from purview_governance.remote_state import capture_remote_state
from purview_governance.remote_state.errors import RemoteStateError
from tests.contract.server import azure_storage_fixture
from tests.remote_state.fakes import FakeReadClient, MutationAttemptError


def test_capture_orders_and_uses_get() -> None:
    client = FakeReadClient(
        list_items=[
            {"name": "zetaSource"},
            {"name": "alphaSource"},
        ],
        get_bodies={
            "alphaSource": azure_storage_fixture("alphaSource"),
            "zetaSource": azure_storage_fixture("zetaSource"),
        },
    )
    state = capture_remote_state(client)
    assert [ds.name for ds in state.data_sources] == ["alphaSource", "zetaSource"]
    assert client.get_calls == ["alphaSource", "zetaSource"]
    assert state.material_state_identity.startswith("sha256:")


def test_capture_duplicate_names_fail_closed() -> None:
    client = FakeReadClient(
        list_items=[{"name": "alphaSource"}, {"name": "alphaSource"}],
        get_bodies={},
    )
    with pytest.raises(RemoteStateError) as exc:
        capture_remote_state(client)
    assert exc.value.code == "remote_state.duplicate_name"


def test_capture_unsupported_kind_accounted() -> None:
    client = FakeReadClient(
        list_items=[{"name": "otherSource"}],
        get_bodies={
            "otherSource": {
                "name": "otherSource",
                "kind": "AdlsGen2",
                "creationType": "Manual",
                "properties": {
                    "endpoint": "https://datalake.dfs.core.windows.net/",
                    "collection": {"referenceName": "root"},
                    "dataSourceCollectionMovingState": "Active",
                },
            }
        },
    )
    state = capture_remote_state(client)
    assert state.data_sources == ()
    assert len(state.uninterpreted_data_sources) == 1
    assert state.uninterpreted_data_sources[0].kind == "AdlsGen2"
    assert state.uninterpreted_data_sources[0].reason_code == "remote_state.unsupported_kind"


def test_fake_forbids_mutation() -> None:
    client = FakeReadClient()
    with pytest.raises(MutationAttemptError):
        client._create_or_replace_data_source("x", {})  # noqa: SLF001
