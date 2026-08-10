"""Helpers for execution-result tests."""

from __future__ import annotations

import copy
from typing import Any

from purview_governance.apply.identity import compute_result_identity
from purview_governance.apply.models import (
    ExecutionFailure,
    ExecutionMode,
    ExecutionResult,
    OperationResult,
    build_execution_result_from_parts,
)
from purview_governance.plan import build_governance_plan
from purview_governance.plan.identity import compute_target_context_identity
from tests.plan.helpers import create_config, empty_remote


def sample_hashes() -> dict[str, str]:
    plan = build_governance_plan(create_config(), empty_remote())
    planned_target = plan.target_context.identity
    other_target = compute_target_context_identity("https://other.purview.azure.com")
    return {
        "plan": plan.plan_identity,
        "planned_target": planned_target,
        "other_target": other_target,
        "planned_remote": plan.identities.remote_state,
        "other_remote": "sha256:" + ("a" * 64),
    }


def make_result(
    *,
    status: str,
    mode: ExecutionMode = ExecutionMode.APPLY,
    execution_target: str | None = None,
    observed: str | None = None,
    performed: int = 0,
    attempted: int = 0,
    unknown: int = 0,
    operations: tuple[OperationResult, ...] | None = None,
    failure_code: str | None = None,
    planned_target: str | None = None,
    planned_remote: str | None = None,
    plan_identity: str | None = None,
) -> ExecutionResult:
    hashes = sample_hashes()
    if planned_target is None:
        planned_target = hashes["planned_target"]
    if planned_remote is None:
        planned_remote = hashes["planned_remote"]
    if plan_identity is None:
        plan_identity = hashes["plan"]
    if operations is None:
        operations = ()
    failure = None if failure_code is None else ExecutionFailure(code=failure_code)
    return build_execution_result_from_parts(
        plan_identity=plan_identity,
        planned_target_context_identity=planned_target,
        execution_target_context_identity=execution_target,
        planned_remote_state_identity=planned_remote,
        observed_remote_state_identity=observed,
        mode=mode,
        status=status,  # type: ignore[arg-type]
        writes_performed=performed,
        writes_attempted=attempted,
        writes_unknown=unknown,
        operations=operations,
        failure=failure,
    )


def recompute_result_identity(document: dict[str, Any]) -> dict[str, Any]:
    mutated = copy.deepcopy(document)
    without = {key: value for key, value in mutated.items() if key != "resultIdentity"}
    mutated["resultIdentity"] = compute_result_identity(without)
    return mutated
