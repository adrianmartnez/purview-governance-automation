"""Config desired Data Source endpoint safety tests."""

from __future__ import annotations

import json
import traceback

import pytest

from purview_governance.config import ConfigValidationError, validate_config_text
from purview_governance.data_source_endpoint import DataSourceEndpointError
from purview_governance.desired.models import DataSourceDesiredState, DesiredState
from purview_governance.diff import diff_desired_vs_remote
from purview_governance.remote_state.models import (
    NormalizedDataSource,
    ObservedProperties,
    build_remote_state,
)

SENTINEL = "SECRET_ENDPOINT_SENTINEL_7f91"

BASE = {
    "apiVersion": "purview-governance-config/v1",
    "target": {"endpoint": "https://contoso-fictional.purview.azure.com"},
    "authentication": {"strategy": "defaultAzureCredential"},
}


def _config_with_endpoint(endpoint: str) -> str:
    doc = {
        **BASE,
        "resources": [
            {
                "type": "dataSource",
                "name": "example-azure-storage",
                "kind": "AzureStorage",
                "properties": {
                    "endpoint": endpoint,
                    "collection": {"referenceName": "Collection-rZX"},
                },
            }
        ],
    }
    return json.dumps(doc)


def _assert_sanitized(exc: BaseException) -> None:
    assert SENTINEL not in str(exc)
    assert SENTINEL not in repr(exc)
    assert SENTINEL not in "".join(traceback.format_exception(exc))
    assert exc.__cause__ is None
    assert exc.__context__ is None


@pytest.mark.parametrize(
    "endpoint",
    [
        f"https://user:{SENTINEL}@example.blob.core.windows.net/",
        f"https://example.blob.core.windows.net/?sv=1&sig={SENTINEL}",
        f"https://example.blob.core.windows.net/#{SENTINEL}",
        "http://example.blob.core.windows.net/",
    ],
)
def test_config_rejects_unsafe_data_source_endpoint(endpoint: str) -> None:
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config_text(_config_with_endpoint(endpoint), format_hint="json")
    diag = exc_info.value.diagnostics[0]
    assert diag.code == "config.invalid_data_source_endpoint"
    assert diag.path == "/resources/0/properties/endpoint"
    _assert_sanitized(exc_info.value)


def test_desired_model_and_diff_cannot_emit_unsafe_endpoint() -> None:
    unsafe = f"https://example.blob.core.windows.net/?sig={SENTINEL}"
    with pytest.raises(DataSourceEndpointError) as exc_info:
        DataSourceDesiredState(
            name="alphaSource",
            kind="AzureStorage",
            endpoint=unsafe,
            collection_reference_name="Collection-rZX",
        )
    _assert_sanitized(exc_info.value)

    # Diff path uses validated models only; constructing unsafe desired fails first.
    remote = build_remote_state(
        (
            NormalizedDataSource(
                name="alphaSource",
                kind="AzureStorage",
                creation_type="Manual",
                endpoint="https://example.blob.core.windows.net/",
                collection_reference_name="Collection-rZX",
                collection_moving_state="Active",
                observed=ObservedProperties(),
            ),
        ),
        (),
    )
    with pytest.raises(DataSourceEndpointError):
        desired = DesiredState(
            data_sources=(
                DataSourceDesiredState(
                    name="alphaSource",
                    kind="AzureStorage",
                    endpoint=unsafe,
                    collection_reference_name="Collection-rZX",
                ),
            )
        )
        diff_desired_vs_remote(desired, remote)

    # Safe endpoint-only replace still works with before/after.
    desired_safe = DesiredState(
        data_sources=(
            DataSourceDesiredState(
                name="alphaSource",
                kind="AzureStorage",
                endpoint="https://other.blob.core.windows.net/",
                collection_reference_name="Collection-rZX",
            ),
        )
    )
    doc = diff_desired_vs_remote(desired_safe, remote)
    assert doc.items[0].outcome == "replace"
    assert doc.items[0].reasons[0].before == "https://example.blob.core.windows.net/"
    assert doc.items[0].reasons[0].after == "https://other.blob.core.windows.net/"
    assert SENTINEL not in doc.to_canonical_json()
