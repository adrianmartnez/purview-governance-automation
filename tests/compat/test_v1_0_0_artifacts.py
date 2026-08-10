"""Frozen v1.0.0 fixture compatibility across config, remote-state, plan, and apply."""

from __future__ import annotations

import json
from pathlib import Path

from purview_governance.apply import execute_governance_plan, load_execution_result_text
from purview_governance.apply.models import ExecutionMode
from purview_governance.config import validate_config_file, validate_config_text
from purview_governance.plan import load_plan_file, load_plan_text
from purview_governance.remote_state.models import (
    NormalizedDataSource,
    ObservedProperties,
    build_remote_state,
)
from tests.contract.client_helpers import make_loopback_client
from tests.contract.server import azure_storage_fixture, start_contract_server

_FIXTURE_DIR = Path(__file__).resolve().parent / "v1_0_0"
_REMOTE_STATE = _FIXTURE_DIR / "remote-state.json"
_CONFIG = _FIXTURE_DIR / "config.yaml"
_PLAN = _FIXTURE_DIR / "plan.json"
_EXECUTION_RESULT = _FIXTURE_DIR / "execution-result.json"


def test_v1_0_0_remote_state_material_identity_unchanged() -> None:
    document = json.loads(_REMOTE_STATE.read_text(encoding="utf-8"))
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


def test_v1_0_0_config_canonical_semantics() -> None:
    config = validate_config_file(_CONFIG)
    assert config.api_version == "purview-governance-config/v1"
    assert config.target.endpoint == "https://account.purview.azure.com"
    assert len(config.resources) == 1
    resource = config.resources[0]
    assert resource.name == "example-source"
    assert resource.kind == "AzureStorage"
    assert resource.endpoint == "https://example.blob.core.windows.net/"
    assert resource.collection_reference_name == "root"

    text = _CONFIG.read_text(encoding="utf-8")
    again = validate_config_text(text, format_hint="yaml")
    assert again.to_document() == config.to_document()


def test_v1_0_0_plan_identity_stable_across_load_and_reserialize() -> None:
    plan = load_plan_file(_PLAN)
    assert plan.api_version == "purview-governance-plan/v1"
    expected_identity = plan.plan_identity
    assert expected_identity == (
        "sha256:7bde6342ff63dd0c73ec89a08a382df37b10a0cb5b3fb2d8b456ee558700fb5e"
    )
    assert plan.desired_state.data_sources[0].name == "example-source"
    assert plan.desired_state.data_sources[0].endpoint == ("https://example.blob.core.windows.net/")
    assert plan.desired_state.data_sources[0].collection_reference_name == "root"

    canonical = plan.to_canonical_json()
    reloaded = load_plan_text(canonical)
    assert reloaded.plan_identity == expected_identity
    assert reloaded.to_canonical_json() == canonical


def _matching_remote_body() -> dict:
    return azure_storage_fixture(
        "example-source",
        endpoint="https://example.blob.core.windows.net/",
        collection_ref="root",
        creation_type="Manual",
        moving_state="Active",
    )


def test_v1_0_0_apply_dry_run_accepts_frozen_plan_against_matching_remote() -> None:
    plan = load_plan_file(_PLAN)
    body = _matching_remote_body()
    with (
        start_contract_server(
            list_mode="example_source",
            get_mode="success",
            get_bodies={"example-source": body},
        ) as server,
        make_loopback_client(server.base_url) as client,
    ):
        result = execute_governance_plan(plan, client, mode=ExecutionMode.DRY_RUN)

    assert result.status == "dry-run-ready"
    assert result.writes_attempted == 0
    assert result.writes_performed == 0
    assert all(op.resource_type == "dataSource" for op in result.operations)

    canonical = result.to_canonical_json()
    reloaded = load_execution_result_text(canonical)
    assert reloaded.result_identity == result.result_identity

    frozen = load_execution_result_text(_EXECUTION_RESULT.read_text(encoding="utf-8"))
    assert frozen.result_identity == result.result_identity
    assert frozen.to_canonical_json() == canonical
