"""Read-only Purview Data Source remote-state capture (List + Get)."""

from __future__ import annotations

from typing import Any, Protocol

from jsonschema import Draft202012Validator

from purview_governance.remote_state.errors import RemoteStateError
from purview_governance.remote_state.models import (
    NormalizedDataSource,
    RemoteState,
    UninterpretedDataSource,
    build_remote_state,
)
from purview_governance.remote_state.normalize import (
    extract_list_item_name,
    normalize_azure_storage_get,
    reject_sensitive_keys,
)
from purview_governance.remote_state.policy import SUPPORTED_KIND
from purview_governance.remote_state.schema import load_remote_state_v1_schema
from purview_governance.scanning.client import DataSourceListResult
from purview_governance.scanning.names import validate_data_source_name


class DataSourceReadClient(Protocol):
    """Minimal read-only seam used by remote-state capture."""

    def list_data_sources(self) -> DataSourceListResult: ...

    def get_data_source(self, name: str) -> dict[str, Any]: ...


def _validate_artifact(document: dict[str, Any]) -> None:
    schema = load_remote_state_v1_schema()
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(document), key=lambda e: list(e.absolute_path))
    if errors:
        raise RemoteStateError(
            "remote_state.artifact_serialization_failed",
            "normalized remote-state artifact failed schema validation",
        )


def capture_remote_state(client: DataSourceReadClient) -> RemoteState:
    """Capture purview-remote-state/v1 via List discovery and authoritative Get.

    Read-only: never calls create-or-replace / PUT / delete.
    """
    listed = client.list_data_sources()
    names: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(listed.items):
        name = extract_list_item_name(item, index=index)
        if name in seen:
            raise RemoteStateError(
                "remote_state.duplicate_name",
                "duplicate Data Source name in list results",
                path=f"/value/{index}/name",
            )
        seen.add(name)
        names.append(name)

    names.sort()
    normalized: list[NormalizedDataSource] = []
    uninterpreted: list[UninterpretedDataSource] = []

    for name in names:
        # Re-validate before Get path construction (defense in depth).
        validate_data_source_name(name)
        body = client.get_data_source(name)
        if not isinstance(body, dict):
            raise RemoteStateError(
                "remote_state.invalid_shape",
                "GET response must be a JSON object",
            )
        reject_sensitive_keys(body)

        kind = body.get("kind")
        if kind is None:
            raise RemoteStateError(
                "remote_state.missing_kind",
                "GET response is missing kind",
                path="/kind",
            )
        if not isinstance(kind, str):
            raise RemoteStateError(
                "remote_state.invalid_kind",
                "kind must be a string",
                path="/kind",
            )
        if kind != SUPPORTED_KIND:
            # Account without pretending material normalization.
            # Still verify identity match when name is present.
            remote_name = body.get("name")
            if remote_name is None:
                raise RemoteStateError(
                    "remote_state.identity_mismatch",
                    "GET response is missing name",
                    path="/name",
                )
            if not isinstance(remote_name, str) or remote_name != name:
                raise RemoteStateError(
                    "remote_state.identity_mismatch",
                    "GET response name does not match the requested dataSourceName",
                    path="/name",
                )
            uninterpreted.append(
                UninterpretedDataSource(
                    name=name,
                    kind=kind,
                    reason_code="remote_state.unsupported_kind",
                )
            )
            continue

        normalized.append(normalize_azure_storage_get(body, requested_name=name))

    state = build_remote_state(tuple(normalized), tuple(uninterpreted))
    try:
        _validate_artifact(state.to_document())
    except RemoteStateError:
        raise
    except Exception:
        raise RemoteStateError(
            "remote_state.artifact_serialization_failed",
            "failed to validate remote-state artifact",
        ) from None
    return state
