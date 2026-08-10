"""Semantic integrity tests for purview-execution-result/v1."""

from __future__ import annotations

import json

import pytest

from purview_governance.apply import (
    ExecutionMode,
    ExecutionResultIntegrityError,
    load_execution_result_text,
)
from purview_governance.apply.models import OperationResult
from tests.apply.helpers import make_result, recompute_result_identity, sample_hashes


def test_dry_run_ready_roundtrip() -> None:
    hashes = sample_hashes()
    result = make_result(
        status="dry-run-ready",
        mode=ExecutionMode.DRY_RUN,
        execution_target=hashes["planned_target"],
        observed=hashes["planned_remote"],
    )
    loaded = load_execution_result_text(result.to_canonical_json())
    assert loaded.to_canonical_json() == result.to_canonical_json()


def test_applied_zero_ops() -> None:
    hashes = sample_hashes()
    result = make_result(
        status="applied",
        execution_target=hashes["planned_target"],
        observed=hashes["planned_remote"],
    )
    load_execution_result_text(result.to_canonical_json())


def test_wrong_target_equal_identities_rejected() -> None:
    hashes = sample_hashes()
    result = make_result(
        status="wrong-target",
        execution_target=hashes["planned_target"],
        failure_code="apply.wrong_target",
    )
    with pytest.raises(ExecutionResultIntegrityError):
        load_execution_result_text(result.to_canonical_json())


def test_wrong_target_missing_execution_rejected() -> None:
    result = make_result(
        status="wrong-target",
        execution_target=None,
        failure_code="apply.wrong_target",
    )
    with pytest.raises(ExecutionResultIntegrityError):
        load_execution_result_text(result.to_canonical_json())


def test_wrong_target_valid_mismatch_accepted() -> None:
    hashes = sample_hashes()
    result = make_result(
        status="wrong-target",
        execution_target=hashes["other_target"],
        failure_code="apply.wrong_target",
    )
    load_execution_result_text(result.to_canonical_json())


def test_applied_target_mismatch_rejected() -> None:
    hashes = sample_hashes()
    result = make_result(
        status="applied",
        execution_target=hashes["other_target"],
        observed=hashes["planned_remote"],
    )
    with pytest.raises(ExecutionResultIntegrityError):
        load_execution_result_text(result.to_canonical_json())


def test_blocked_with_execution_target_rejected() -> None:
    hashes = sample_hashes()
    result = make_result(
        status="blocked",
        mode=ExecutionMode.DRY_RUN,
        execution_target=hashes["planned_target"],
        failure_code="apply.plan_blocked",
    )
    with pytest.raises(ExecutionResultIntegrityError):
        load_execution_result_text(result.to_canonical_json())


def test_applied_observed_null_rejected() -> None:
    hashes = sample_hashes()
    result = make_result(
        status="applied",
        execution_target=hashes["planned_target"],
        observed=None,
    )
    with pytest.raises(ExecutionResultIntegrityError):
        load_execution_result_text(result.to_canonical_json())


def test_applied_observed_mismatch_rejected() -> None:
    hashes = sample_hashes()
    result = make_result(
        status="applied",
        execution_target=hashes["planned_target"],
        observed=hashes["other_remote"],
    )
    with pytest.raises(ExecutionResultIntegrityError):
        load_execution_result_text(result.to_canonical_json())


def test_stale_equal_observed_rejected() -> None:
    hashes = sample_hashes()
    result = make_result(
        status="stale",
        execution_target=hashes["planned_target"],
        observed=hashes["planned_remote"],
        failure_code="apply.stale_plan",
    )
    with pytest.raises(ExecutionResultIntegrityError):
        load_execution_result_text(result.to_canonical_json())


def test_failed_before_write_observed_non_null_rejected() -> None:
    hashes = sample_hashes()
    result = make_result(
        status="failed-before-write",
        execution_target=hashes["planned_target"],
        observed=hashes["planned_remote"],
        failure_code="apply.remote_read_failed",
    )
    with pytest.raises(ExecutionResultIntegrityError):
        load_execution_result_text(result.to_canonical_json())


def test_write_failed_first_op() -> None:
    hashes = sample_hashes()
    ops = (
        OperationResult(
            sequence=1,
            resource_type="dataSource",
            name="example-source",
            action="create",
            status="failed",
        ),
    )
    result = make_result(
        status="write-failed",
        execution_target=hashes["planned_target"],
        observed=hashes["planned_remote"],
        performed=0,
        attempted=1,
        operations=ops,
        failure_code="apply.write_rejected",
    )
    load_execution_result_text(result.to_canonical_json())


def test_write_failed_without_failed_op_rejected() -> None:
    hashes = sample_hashes()
    result = make_result(
        status="write-failed",
        execution_target=hashes["planned_target"],
        observed=hashes["planned_remote"],
        performed=0,
        attempted=1,
        operations=(),
        failure_code="apply.write_rejected",
    )
    with pytest.raises(ExecutionResultIntegrityError):
        load_execution_result_text(result.to_canonical_json())


def test_status_failure_code_mismatch_rejected() -> None:
    hashes = sample_hashes()
    result = make_result(
        status="stale",
        execution_target=hashes["planned_target"],
        observed=hashes["other_remote"],
        failure_code="apply.write_rejected",
    )
    with pytest.raises(ExecutionResultIntegrityError):
        load_execution_result_text(result.to_canonical_json())


def test_success_with_failure_rejected() -> None:
    hashes = sample_hashes()
    result = make_result(
        status="dry-run-ready",
        mode=ExecutionMode.DRY_RUN,
        execution_target=hashes["planned_target"],
        observed=hashes["planned_remote"],
        failure_code="apply.plan_blocked",
    )
    with pytest.raises(ExecutionResultIntegrityError):
        load_execution_result_text(result.to_canonical_json())


def test_pretty_json_accepted() -> None:
    sample_hashes()
    result = make_result(
        status="blocked",
        mode=ExecutionMode.DRY_RUN,
        failure_code="apply.plan_blocked",
    )
    pretty = json.dumps(json.loads(result.to_canonical_json()), indent=2, ensure_ascii=False)
    loaded = load_execution_result_text(pretty)
    assert loaded.to_canonical_json() == result.to_canonical_json()


def test_result_identity_tamper_rejected() -> None:
    sample_hashes()
    result = make_result(
        status="blocked",
        mode=ExecutionMode.DRY_RUN,
        failure_code="apply.plan_blocked",
    )
    document = result.to_document()
    document["resultIdentity"] = "sha256:" + ("b" * 64)
    with pytest.raises(ExecutionResultIntegrityError):
        load_execution_result_text(json.dumps(document))


def test_failed_before_write_with_attempted_rejected() -> None:
    hashes = sample_hashes()
    document = make_result(
        status="failed-before-write",
        execution_target=hashes["planned_target"],
        failure_code="apply.remote_read_failed",
    ).to_document()
    document["writesAttempted"] = 1
    document = recompute_result_identity(document)
    with pytest.raises(ExecutionResultIntegrityError):
        load_execution_result_text(json.dumps(document))


def _op(sequence: int, status: str, *, name: str = "example-source") -> OperationResult:
    return OperationResult(
        sequence=sequence,
        resource_type="dataSource",
        name=name,
        action="create",
        status=status,  # type: ignore[arg-type]
    )


def test_write_failed_not_run_before_failed_rejected() -> None:
    hashes = sample_hashes()
    document = make_result(
        status="write-failed",
        execution_target=hashes["planned_target"],
        observed=hashes["planned_remote"],
        performed=0,
        attempted=1,
        operations=(_op(1, "not-run"), _op(2, "failed", name="other-source")),
        failure_code="apply.write_rejected",
    ).to_document()
    document = recompute_result_identity(document)
    with pytest.raises(ExecutionResultIntegrityError) as exc:
        load_execution_result_text(json.dumps(document))
    assert exc.value.code == "apply.invalid_result_operations"


def test_write_failed_gap_before_failed_rejected() -> None:
    hashes = sample_hashes()
    document = make_result(
        status="write-failed",
        execution_target=hashes["planned_target"],
        observed=hashes["planned_remote"],
        performed=1,
        attempted=2,
        operations=(
            _op(1, "succeeded"),
            _op(2, "not-run", name="mid-source"),
            _op(3, "failed", name="other-source"),
        ),
        failure_code="apply.write_rejected",
    ).to_document()
    document = recompute_result_identity(document)
    with pytest.raises(ExecutionResultIntegrityError) as exc:
        load_execution_result_text(json.dumps(document))
    assert exc.value.code == "apply.invalid_result_operations"


def test_indeterminate_not_run_before_unknown_rejected() -> None:
    hashes = sample_hashes()
    document = make_result(
        status="indeterminate",
        execution_target=hashes["planned_target"],
        observed=hashes["planned_remote"],
        performed=0,
        attempted=1,
        unknown=1,
        operations=(_op(1, "not-run"), _op(2, "unknown", name="other-source")),
        failure_code="apply.write_outcome_unknown",
    ).to_document()
    document = recompute_result_identity(document)
    with pytest.raises(ExecutionResultIntegrityError) as exc:
        load_execution_result_text(json.dumps(document))
    assert exc.value.code == "apply.invalid_result_operations"


def test_indeterminate_gap_before_unknown_rejected() -> None:
    hashes = sample_hashes()
    document = make_result(
        status="indeterminate",
        execution_target=hashes["planned_target"],
        observed=hashes["planned_remote"],
        performed=1,
        attempted=2,
        unknown=1,
        operations=(
            _op(1, "succeeded"),
            _op(2, "not-run", name="mid-source"),
            _op(3, "unknown", name="other-source"),
        ),
        failure_code="apply.write_outcome_unknown",
    ).to_document()
    document = recompute_result_identity(document)
    with pytest.raises(ExecutionResultIntegrityError) as exc:
        load_execution_result_text(json.dumps(document))
    assert exc.value.code == "apply.invalid_result_operations"


def test_write_failed_contiguous_patterns_accepted() -> None:
    hashes = sample_hashes()
    first = make_result(
        status="write-failed",
        execution_target=hashes["planned_target"],
        observed=hashes["planned_remote"],
        performed=0,
        attempted=1,
        operations=(_op(1, "failed"), _op(2, "not-run", name="other-source")),
        failure_code="apply.write_rejected",
    )
    load_execution_result_text(first.to_canonical_json())

    second = make_result(
        status="write-failed",
        execution_target=hashes["planned_target"],
        observed=hashes["planned_remote"],
        performed=1,
        attempted=2,
        operations=(
            _op(1, "succeeded"),
            _op(2, "failed", name="mid-source"),
            _op(3, "not-run", name="other-source"),
        ),
        failure_code="apply.write_rejected",
    )
    load_execution_result_text(second.to_canonical_json())


def test_indeterminate_contiguous_patterns_accepted() -> None:
    hashes = sample_hashes()
    first = make_result(
        status="indeterminate",
        execution_target=hashes["planned_target"],
        observed=hashes["planned_remote"],
        performed=0,
        attempted=1,
        unknown=1,
        operations=(_op(1, "unknown"), _op(2, "not-run", name="other-source")),
        failure_code="apply.write_outcome_unknown",
    )
    load_execution_result_text(first.to_canonical_json())

    second = make_result(
        status="indeterminate",
        execution_target=hashes["planned_target"],
        observed=hashes["planned_remote"],
        performed=1,
        attempted=2,
        unknown=1,
        operations=(
            _op(1, "succeeded"),
            _op(2, "unknown", name="mid-source"),
            _op(3, "not-run", name="other-source"),
        ),
        failure_code="apply.write_outcome_unknown",
    )
    load_execution_result_text(second.to_canonical_json())
