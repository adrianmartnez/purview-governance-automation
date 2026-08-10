"""Closed DiffReason shape and outcome compatibility tests."""

from __future__ import annotations

import copy
import json

import pytest

from purview_governance.plan import PlanIntegrityError, build_governance_plan, load_plan_text
from purview_governance.remote_state.models import build_remote_state
from tests.plan.helpers import create_config, empty_remote, recompute_plan_identity, remote_ds


def _load_mutated(mutate) -> None:
    document = build_governance_plan(create_config(), empty_remote()).to_document()
    mutate(document)
    document = recompute_plan_identity(document)
    # Desired/material identities may also need refresh when desired/changeSet change.
    from purview_governance.plan.identity import (
        compute_desired_state_identity,
        compute_material_configuration_identity,
        compute_target_context_identity,
    )

    desired_id = compute_desired_state_identity(document["desiredState"])
    target_id = compute_target_context_identity(document["targetContext"]["endpoint"])
    document["identities"]["desiredState"] = desired_id
    document["identities"]["materialConfiguration"] = compute_material_configuration_identity(
        target_context_identity=target_id,
        desired_state_identity=desired_id,
    )
    document["targetContext"]["identity"] = target_id
    document = recompute_plan_identity(document)
    load_plan_text(json.dumps(document))


def test_noop_with_reason_rejected() -> None:
    remote = build_remote_state((remote_ds(),), ())
    document = build_governance_plan(create_config(), remote).to_document()
    document["changeSet"]["items"][0]["reasons"] = [{"code": "desired.absent_remote", "path": "/"}]
    document = recompute_plan_identity(document)
    with pytest.raises(PlanIntegrityError) as exc_info:
        load_plan_text(json.dumps(document))
    assert exc_info.value.code == "plan.invalid_reason_outcome"


def test_create_with_endpoint_changed_rejected() -> None:
    document = build_governance_plan(create_config(), empty_remote()).to_document()
    document["changeSet"]["items"][0]["reasons"] = [
        {
            "code": "properties.endpoint.changed",
            "path": "/properties/endpoint",
            "before": "https://old.blob.core.windows.net/",
            "after": "https://example.blob.core.windows.net/",
        }
    ]
    document = recompute_plan_identity(document)
    with pytest.raises(PlanIntegrityError) as exc_info:
        load_plan_text(json.dumps(document))
    assert exc_info.value.code == "plan.invalid_reason_outcome"


def test_replace_with_absent_remote_rejected() -> None:
    remote = build_remote_state(
        (remote_ds(endpoint="https://old.blob.core.windows.net/"),),
        (),
    )
    document = build_governance_plan(create_config(), remote).to_document()
    document["changeSet"]["items"][0]["reasons"] = [{"code": "desired.absent_remote", "path": "/"}]
    document = recompute_plan_identity(document)
    with pytest.raises(PlanIntegrityError) as exc_info:
        load_plan_text(json.dumps(document))
    assert exc_info.value.code == "plan.invalid_reason_outcome"


def test_replace_with_two_reasons_rejected() -> None:
    remote = build_remote_state(
        (remote_ds(endpoint="https://old.blob.core.windows.net/"),),
        (),
    )
    document = build_governance_plan(create_config(), remote).to_document()
    document["changeSet"]["items"][0]["reasons"] = [
        {
            "code": "properties.endpoint.changed",
            "path": "/properties/endpoint",
            "before": "https://old.blob.core.windows.net/",
            "after": "https://example.blob.core.windows.net/",
        },
        {"code": "desired.absent_remote", "path": "/"},
    ]
    document = recompute_plan_identity(document)
    with pytest.raises(PlanIntegrityError) as exc_info:
        load_plan_text(json.dumps(document))
    assert exc_info.value.code in {"plan.invalid_reason_outcome", "plan.noncanonical_input"}


def test_remote_only_missing_absent_desired_rejected() -> None:
    from purview_governance.config import validate_config_text

    empty = validate_config_text(
        """
apiVersion: purview-governance-config/v1
target:
  endpoint: https://account.purview.azure.com
authentication:
  strategy: defaultAzureCredential
resources: []
""",
        format_hint="yaml",
    )
    remote = build_remote_state((remote_ds(name="unmanaged"),), ())
    document = build_governance_plan(empty, remote).to_document()
    document["changeSet"]["items"][0]["reasons"] = []
    document = recompute_plan_identity(document)
    with pytest.raises(PlanIntegrityError) as exc_info:
        load_plan_text(json.dumps(document))
    assert exc_info.value.code == "plan.invalid_reason_outcome"


def test_remote_only_with_endpoint_changed_rejected() -> None:
    from purview_governance.config import validate_config_text

    empty = validate_config_text(
        """
apiVersion: purview-governance-config/v1
target:
  endpoint: https://account.purview.azure.com
authentication:
  strategy: defaultAzureCredential
resources: []
""",
        format_hint="yaml",
    )
    remote = build_remote_state((remote_ds(name="unmanaged"),), ())
    document = build_governance_plan(empty, remote).to_document()
    document["changeSet"]["items"][0]["reasons"] = [
        {"code": "remote.absent_desired", "path": "/"},
        {
            "code": "properties.endpoint.changed",
            "path": "/properties/endpoint",
            "before": "https://a.blob.core.windows.net/",
            "after": "https://b.blob.core.windows.net/",
        },
    ]
    # sort reasons by path,code
    document["changeSet"]["items"][0]["reasons"].sort(key=lambda r: (r["path"], r["code"]))
    document = recompute_plan_identity(document)
    with pytest.raises(PlanIntegrityError) as exc_info:
        load_plan_text(json.dumps(document))
    assert exc_info.value.code == "plan.invalid_reason_outcome"


def test_blocked_without_blocking_reason_rejected() -> None:
    remote = build_remote_state((remote_ds(creation_type="AutoNative"),), ())
    document = build_governance_plan(create_config(), remote).to_document()
    document["changeSet"]["items"][0]["reasons"] = [{"code": "desired.absent_remote", "path": "/"}]
    document = recompute_plan_identity(document)
    with pytest.raises(PlanIntegrityError) as exc_info:
        load_plan_text(json.dumps(document))
    assert exc_info.value.code == "plan.invalid_reason_outcome"


def test_forbidden_before_on_absent_remote_rejected() -> None:
    document = build_governance_plan(create_config(), empty_remote()).to_document()
    document["changeSet"]["items"][0]["reasons"] = [
        {"code": "desired.absent_remote", "path": "/", "before": "ARBITRARY"}
    ]
    document = recompute_plan_identity(document)
    with pytest.raises(PlanIntegrityError) as exc_info:
        load_plan_text(json.dumps(document))
    assert exc_info.value.code == "plan.invalid_reason"


def test_endpoint_before_equals_after_rejected() -> None:
    remote = build_remote_state(
        (remote_ds(endpoint="https://old.blob.core.windows.net/"),),
        (),
    )
    document = build_governance_plan(create_config(), remote).to_document()
    document["changeSet"]["items"][0]["reasons"][0]["before"] = (
        "https://example.blob.core.windows.net/"
    )
    document["changeSet"]["items"][0]["reasons"][0]["after"] = (
        "https://example.blob.core.windows.net/"
    )
    document = recompute_plan_identity(document)
    with pytest.raises(PlanIntegrityError) as exc_info:
        load_plan_text(json.dumps(document))
    assert exc_info.value.code == "plan.invalid_reason"


def test_unknown_reason_code_rejected() -> None:
    document = build_governance_plan(create_config(), empty_remote()).to_document()
    document["changeSet"]["items"][0]["reasons"] = [{"code": "custom.free_form", "path": "/"}]
    document = recompute_plan_identity(document)
    with pytest.raises(PlanIntegrityError) as exc_info:
        load_plan_text(json.dumps(document))
    assert exc_info.value.code == "plan.invalid_reason"


def test_code_path_mismatch_rejected() -> None:
    document = build_governance_plan(create_config(), empty_remote()).to_document()
    document["changeSet"]["items"][0]["reasons"] = [
        {"code": "desired.absent_remote", "path": "/kind"}
    ]
    document = recompute_plan_identity(document)
    with pytest.raises(PlanIntegrityError) as exc_info:
        load_plan_text(json.dumps(document))
    assert exc_info.value.code == "plan.invalid_reason"


def test_duplicate_reason_rejected() -> None:
    remote = build_remote_state((remote_ds(creation_type="AutoNative"),), ())
    document = build_governance_plan(create_config(), remote).to_document()
    reason = copy.deepcopy(document["changeSet"]["items"][0]["reasons"][0])
    document["changeSet"]["items"][0]["reasons"].append(reason)
    document = recompute_plan_identity(document)
    with pytest.raises(PlanIntegrityError) as exc_info:
        load_plan_text(json.dumps(document))
    assert exc_info.value.code in {"plan.invalid_reason", "plan.noncanonical_input"}


def test_valid_blocked_with_endpoint_changed_accepted() -> None:
    remote = build_remote_state(
        (
            remote_ds(
                creation_type="AutoNative",
                endpoint="https://old.blob.core.windows.net/",
            ),
        ),
        (),
    )
    plan = build_governance_plan(create_config(), remote)
    assert plan.execution_eligibility == "blocked"
    codes = {r.code for r in plan.change_set.items[0].reasons}
    assert "remote.creation_type_auto_native" in codes
    assert "properties.endpoint.changed" in codes
    loaded = load_plan_text(plan.to_canonical_json())
    assert loaded.plan_identity == plan.plan_identity


def test_unsupported_blocked_shapes() -> None:
    from purview_governance.config import validate_config_text
    from purview_governance.remote_state.models import UninterpretedDataSource

    empty = validate_config_text(
        """
apiVersion: purview-governance-config/v1
target:
  endpoint: https://account.purview.azure.com
authentication:
  strategy: defaultAzureCredential
resources: []
""",
        format_hint="yaml",
    )
    remote = build_remote_state(
        (),
        (
            UninterpretedDataSource(
                name="weird-source",
                kind="AdlsGen2",
                reason_code="remote_state.unsupported_kind",
            ),
        ),
    )
    # Without desired: mutate to include kind.changed
    document = build_governance_plan(empty, remote).to_document()
    document["changeSet"]["items"][0]["reasons"] = [
        {"code": "kind.changed", "path": "/kind", "before": "AdlsGen2", "after": "AzureStorage"},
        {
            "code": "remote_state.unsupported_kind",
            "path": "/kind",
            "before": "AdlsGen2",
        },
    ]
    document["changeSet"]["items"][0]["reasons"].sort(key=lambda r: (r["path"], r["code"]))
    document = recompute_plan_identity(document)
    with pytest.raises(PlanIntegrityError) as exc_info:
        load_plan_text(json.dumps(document))
    assert exc_info.value.code == "plan.invalid_reason_outcome"

    # With desired: missing kind.changed
    # create_config has example-source; use same-name unsupported remote:
    remote2 = build_remote_state(
        (),
        (
            UninterpretedDataSource(
                name="example-source",
                kind="AdlsGen2",
                reason_code="remote_state.unsupported_kind",
            ),
        ),
    )
    document2 = build_governance_plan(create_config(), remote2).to_document()
    document2["changeSet"]["items"][0]["reasons"] = [
        {"code": "remote.absent_desired", "path": "/"},
        {
            "code": "remote_state.unsupported_kind",
            "path": "/kind",
            "before": "AdlsGen2",
        },
    ]
    document2["changeSet"]["items"][0]["reasons"].sort(key=lambda r: (r["path"], r["code"]))
    # Mutating reasons only; builder already produced valid summary/ops.
    document2 = recompute_plan_identity(document2)
    with pytest.raises(PlanIntegrityError) as exc_info:
        load_plan_text(json.dumps(document2))
    assert exc_info.value.code == "plan.invalid_reason_outcome"
