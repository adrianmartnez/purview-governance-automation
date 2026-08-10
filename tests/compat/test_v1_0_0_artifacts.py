"""Frozen v1.0.0 fixture compatibility for remote-state identity."""

from __future__ import annotations

import json
from pathlib import Path

from purview_governance.remote_state.models import (
    NormalizedDataSource,
    ObservedProperties,
    build_remote_state,
)

_FIXTURE = Path(__file__).resolve().parent / "v1_0_0" / "remote-state.json"


def test_v1_0_0_remote_state_material_identity_unchanged() -> None:
    document = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    assert document["apiVersion"] == "purview-remote-state/v1"
    expected_identity = document["materialStateIdentity"]

    data_sources = tuple(
        NormalizedDataSource(
            name=item["name"],
            kind="AzureStorage",
            creation_type=item["creationType"],
            endpoint=item["properties"]["endpoint"],
            collection_reference_name=item["properties"]["collection"]["referenceName"],
            collection_moving_state=item["properties"]["dataSourceCollectionMovingState"],
            observed=ObservedProperties(),
        )
        for item in document["dataSources"]
    )
    rebuilt = build_remote_state(data_sources, ())
    assert rebuilt.material_state_identity == expected_identity
    assert rebuilt.to_document()["materialStateIdentity"] == expected_identity
