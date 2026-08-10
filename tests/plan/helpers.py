"""Shared helpers for governance-plan tests."""

from __future__ import annotations

import copy
import json
from typing import Any

from purview_governance.config import validate_config_text
from purview_governance.config.models import (
    AuthenticationConfig,
    DataSourceResourceConfig,
    GovernanceConfig,
    TargetConfig,
)
from purview_governance.plan import build_governance_plan
from purview_governance.plan.identity import (
    compute_desired_state_identity,
    compute_material_configuration_identity,
    compute_plan_identity,
    compute_target_context_identity,
)
from purview_governance.remote_state.canonical import dumps_canonical
from purview_governance.remote_state.models import (
    NormalizedDataSource,
    ObservedProperties,
    UnknownLegacyMovingState,
    build_remote_state,
)

EMPTY_CONFIG_YAML = """
apiVersion: purview-governance-config/v1
target:
  endpoint: https://account.purview.azure.com
authentication:
  strategy: defaultAzureCredential
resources: []
"""

CREATE_CONFIG_YAML = """
apiVersion: purview-governance-config/v1
target:
  endpoint: https://account.purview.azure.com
authentication:
  strategy: defaultAzureCredential
resources:
  - type: dataSource
    name: example-source
    kind: AzureStorage
    properties:
      endpoint: https://example.blob.core.windows.net/
      collection:
        referenceName: root
"""


def empty_config() -> GovernanceConfig:
    return validate_config_text(EMPTY_CONFIG_YAML, format_hint="yaml")


def create_config() -> GovernanceConfig:
    return validate_config_text(CREATE_CONFIG_YAML, format_hint="yaml")


def config_with_resources(*resources: DataSourceResourceConfig) -> GovernanceConfig:
    return GovernanceConfig(
        api_version="purview-governance-config/v1",
        target=TargetConfig(endpoint="https://account.purview.azure.com"),
        authentication=AuthenticationConfig(strategy="defaultAzureCredential"),
        resources=resources,
    )


def remote_ds(
    name: str = "example-source",
    *,
    creation_type: str = "Manual",
    moving: str | UnknownLegacyMovingState = "Active",
    endpoint: str = "https://example.blob.core.windows.net/",
    collection: str = "root",
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


def empty_remote():
    return build_remote_state((), ())


def plan_document_from_build(**kwargs: Any) -> dict[str, Any]:
    config = kwargs.get("config", create_config())
    remote = kwargs.get("remote", empty_remote())
    plan = build_governance_plan(config, remote)
    return plan.to_document()


def recompute_plan_identity(document: dict[str, Any]) -> dict[str, Any]:
    mutated = copy.deepcopy(document)
    without = {key: value for key, value in mutated.items() if key != "planIdentity"}
    mutated["planIdentity"] = compute_plan_identity(without)
    return mutated


def refresh_plan_identities(document: dict[str, Any]) -> dict[str, Any]:
    """Recompute target/desired/material/plan identities after document mutations."""
    mutated = copy.deepcopy(document)
    endpoint = mutated["targetContext"]["endpoint"]
    target_id = compute_target_context_identity(endpoint)
    desired_id = compute_desired_state_identity(mutated["desiredState"])
    mutated["targetContext"]["identity"] = target_id
    mutated["identities"]["desiredState"] = desired_id
    mutated["identities"]["materialConfiguration"] = compute_material_configuration_identity(
        target_context_identity=target_id,
        desired_state_identity=desired_id,
    )
    return recompute_plan_identity(mutated)


def dumps_pretty(document: dict[str, Any]) -> str:
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def dumps_reordered(document: dict[str, Any]) -> str:
    # Force a non-sorted top-level key order distinct from dumps_canonical.
    ordered = {
        "summary": document["summary"],
        "planIdentity": document["planIdentity"],
        "operations": document["operations"],
        "executionEligibility": document["executionEligibility"],
        "changeSet": document["changeSet"],
        "desiredState": document["desiredState"],
        "identities": document["identities"],
        "targetContext": document["targetContext"],
        "configurationApiVersion": document["configurationApiVersion"],
        "apiVersion": document["apiVersion"],
    }
    return json.dumps(ordered, ensure_ascii=False)


def canonical_bytes(document: dict[str, Any]) -> str:
    return dumps_canonical(document)
