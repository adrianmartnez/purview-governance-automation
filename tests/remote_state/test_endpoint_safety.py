"""Remote-state must fail closed on credential-bearing material endpoints."""

from __future__ import annotations

import traceback

import pytest

from purview_governance.data_source_endpoint import DataSourceEndpointError
from purview_governance.remote_state.errors import RemoteStateError
from purview_governance.remote_state.models import (
    NormalizedDataSource,
    ObservedProperties,
    build_remote_state,
)
from purview_governance.remote_state.normalize import normalize_azure_storage_get
from purview_governance.remote_state.service import capture_remote_state
from tests.contract.server import azure_storage_fixture
from tests.remote_state.fakes import FakeReadClient

SENTINEL = "SECRET_ENDPOINT_SENTINEL_7f91"


def _assert_sanitized(exc: BaseException) -> None:
    assert SENTINEL not in str(exc)
    assert SENTINEL not in repr(exc)
    assert SENTINEL not in "".join(traceback.format_exception(exc))
    assert exc.__cause__ is None
    assert exc.__context__ is None
    for attr in vars(exc).values():
        if isinstance(attr, str):
            assert SENTINEL not in attr


@pytest.mark.parametrize(
    "endpoint",
    [
        f"https://user:{SENTINEL}@example.blob.core.windows.net/",
        f"https://example.blob.core.windows.net/?sv=1&sig={SENTINEL}",
        f"https://example.blob.core.windows.net/#{SENTINEL}",
        "http://example.blob.core.windows.net/",
        "https:///no-host",
        "https://[::1",
        "https://example.blob.core.windows.net:notaport/",
    ],
)
def test_remote_normalize_rejects_unsafe_endpoint(endpoint: str) -> None:
    body = azure_storage_fixture("alphaSource", endpoint=endpoint)
    with pytest.raises(RemoteStateError) as exc_info:
        normalize_azure_storage_get(body, requested_name="alphaSource")
    assert exc_info.value.code == "remote_state.invalid_endpoint"
    _assert_sanitized(exc_info.value)


def test_capture_does_not_produce_artifact_for_unsafe_endpoint() -> None:
    unsafe = f"https://example.blob.core.windows.net/?sig={SENTINEL}"
    client = FakeReadClient(
        list_items=[{"name": "alphaSource"}],
        get_bodies={"alphaSource": azure_storage_fixture("alphaSource", endpoint=unsafe)},
    )
    with pytest.raises(RemoteStateError) as exc_info:
        capture_remote_state(client)
    assert exc_info.value.code == "remote_state.invalid_endpoint"
    _assert_sanitized(exc_info.value)


def test_public_model_rejects_unsafe_endpoint_before_artifact() -> None:
    unsafe = f"https://user:{SENTINEL}@example.blob.core.windows.net/"
    with pytest.raises(DataSourceEndpointError) as exc_info:
        NormalizedDataSource(
            name="alphaSource",
            kind="AzureStorage",
            creation_type="Manual",
            endpoint=unsafe,
            collection_reference_name="Collection-rZX",
            collection_moving_state="Active",
            observed=ObservedProperties(),
        )
    _assert_sanitized(exc_info.value)

    # Safe construction still works; trailing slash preserved.
    ds = NormalizedDataSource(
        name="alphaSource",
        kind="AzureStorage",
        creation_type="Manual",
        endpoint="https://example.blob.core.windows.net/",
        collection_reference_name="Collection-rZX",
        collection_moving_state="Active",
        observed=ObservedProperties(),
    )
    state = build_remote_state((ds,), ())
    assert "https://example.blob.core.windows.net/" in state.to_canonical_json()
    assert SENTINEL not in state.to_canonical_json()
