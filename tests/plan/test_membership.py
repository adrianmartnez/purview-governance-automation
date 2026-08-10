"""Desired/changeSet membership and operation mapping integrity."""

from __future__ import annotations

import json

import pytest

from purview_governance.plan import PlanIntegrityError, build_governance_plan, load_plan_text
from purview_governance.remote_state.models import build_remote_state
from tests.plan.helpers import (
    create_config,
    empty_config,
    empty_remote,
    recompute_plan_identity,
    remote_ds,
)


def test_missing_changeset_item_for_desired_rejected() -> None:
    document = build_governance_plan(create_config(), empty_remote()).to_document()
    document["changeSet"]["items"] = []
    document["operations"] = []
    document["summary"] = {
        "total": 0,
        "create": 0,
        "replace": 0,
        "noOp": 0,
        "remoteOnly": 0,
        "blocked": 0,
        "operations": 0,
    }
    document["executionEligibility"] = "ready"
    document = recompute_plan_identity(document)
    with pytest.raises(PlanIntegrityError) as exc_info:
        load_plan_text(json.dumps(document))
    assert exc_info.value.code == "plan.invalid_membership"


def test_noop_without_desired_rejected() -> None:
    document = build_governance_plan(empty_config(), empty_remote()).to_document()
    document["changeSet"]["items"] = [
        {"name": "ghost-source", "type": "dataSource", "outcome": "no-op", "reasons": []}
    ]
    document["summary"] = {
        "total": 1,
        "create": 0,
        "replace": 0,
        "noOp": 1,
        "remoteOnly": 0,
        "blocked": 0,
        "operations": 0,
    }
    document = recompute_plan_identity(document)
    with pytest.raises(PlanIntegrityError) as exc_info:
        load_plan_text(json.dumps(document))
    assert exc_info.value.code == "plan.invalid_membership"


def test_remote_only_with_desired_rejected() -> None:
    document = build_governance_plan(create_config(), empty_remote()).to_document()
    document["changeSet"]["items"][0]["outcome"] = "remote-only"
    document["changeSet"]["items"][0]["reasons"] = [{"code": "remote.absent_desired", "path": "/"}]
    document["operations"] = []
    document["summary"] = {
        "total": 1,
        "create": 0,
        "replace": 0,
        "noOp": 0,
        "remoteOnly": 1,
        "blocked": 0,
        "operations": 0,
    }
    document = recompute_plan_identity(document)
    with pytest.raises(PlanIntegrityError) as exc_info:
        load_plan_text(json.dumps(document))
    assert exc_info.value.code == "plan.invalid_membership"


def test_blocked_with_and_without_desired_allowed() -> None:
    # with desired
    remote = build_remote_state((remote_ds(creation_type="AutoNative"),), ())
    plan = build_governance_plan(create_config(), remote)
    assert plan.change_set.items[0].outcome == "blocked"
    load_plan_text(plan.to_canonical_json())

    # without desired (unsupported)
    from purview_governance.remote_state.models import UninterpretedDataSource

    remote2 = build_remote_state(
        (),
        (
            UninterpretedDataSource(
                name="weird-source",
                kind="AdlsGen2",
                reason_code="remote_state.unsupported_kind",
            ),
        ),
    )
    plan2 = build_governance_plan(empty_config(), remote2)
    assert plan2.change_set.items[0].outcome == "blocked"
    load_plan_text(plan2.to_canonical_json())


def test_operation_action_mismatch_rejected() -> None:
    document = build_governance_plan(create_config(), empty_remote()).to_document()
    document["operations"][0]["action"] = "replace"
    document = recompute_plan_identity(document)
    with pytest.raises(PlanIntegrityError) as exc_info:
        load_plan_text(json.dumps(document))
    assert exc_info.value.code == "plan.invalid_operation_mapping"


def test_duplicate_operation_rejected() -> None:
    document = build_governance_plan(create_config(), empty_remote()).to_document()
    op = dict(document["operations"][0])
    op["sequence"] = 2
    document["operations"].append(op)
    document["summary"]["operations"] = 2
    document = recompute_plan_identity(document)
    with pytest.raises(PlanIntegrityError) as exc_info:
        load_plan_text(json.dumps(document))
    assert exc_info.value.code == "plan.invalid_operation_mapping"
