"""Schema + semantic integrity for purview-execution-result/v1."""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator

from purview_governance.apply.errors import (
    ExecutionResultIntegrityError,
    ExecutionResultSchemaError,
)
from purview_governance.apply.identity import RESULT_API_VERSION, compute_result_identity
from purview_governance.apply.models import FAILURE_CODES_BY_STATUS
from purview_governance.apply.schema import load_execution_result_v1_schema
from purview_governance.plan.identity import is_sha256_identity
from purview_governance.remote_state.canonical import dumps_canonical


def _integrity(code: str, message: str, *, path: str = "") -> None:
    raise ExecutionResultIntegrityError(code, message, path=path)


def _validate_operation_status_pattern(
    *,
    status: str,
    operations: list[dict[str, Any]],
    writes_performed: int,
    writes_attempted: int,
    writes_unknown: int,
) -> None:
    """Reject any status vector that is not an exact contiguous prefix pattern."""
    actual = [op.get("status") for op in operations]
    n = len(operations)

    if status in {
        "dry-run-ready",
        "blocked",
        "wrong-target",
        "stale",
        "failed-before-write",
    }:
        expected = ["not-run"] * n
    elif status == "applied":
        expected = ["succeeded"] * n
    elif status == "write-failed":
        if writes_attempted != writes_performed + 1:
            _integrity(
                "apply.invalid_result_counters",
                "write-failed requires attempted=performed+1",
            )
        if writes_performed < 0 or writes_performed + 1 > n:
            _integrity(
                "apply.invalid_result_operations",
                "write-failed performed count is inconsistent with operations",
            )
        if n == 0:
            _integrity(
                "apply.invalid_result_operations",
                "write-failed requires at least one operation",
            )
        expected = (
            ["succeeded"] * writes_performed + ["failed"] + ["not-run"] * (n - writes_performed - 1)
        )
    elif status == "indeterminate":
        if writes_attempted != writes_performed + 1 or writes_unknown != 1:
            _integrity(
                "apply.invalid_result_counters",
                "indeterminate requires attempted=performed+1 and unknown=1",
            )
        if writes_performed < 0 or writes_performed + 1 > n:
            _integrity(
                "apply.invalid_result_operations",
                "indeterminate performed count is inconsistent with operations",
            )
        if n == 0:
            _integrity(
                "apply.invalid_result_operations",
                "indeterminate requires at least one operation",
            )
        expected = (
            ["succeeded"] * writes_performed
            + ["unknown"]
            + ["not-run"] * (n - writes_performed - 1)
        )
    else:
        _integrity("apply.invalid_result_status", "unknown execution status", path="/status")

    if actual != expected:
        _integrity(
            "apply.invalid_result_operations",
            "operation statuses must form the exact contiguous execution pattern",
            path="/operations",
        )


def validate_result_document_schema(document: dict[str, Any]) -> None:
    schema_failed = False
    try:
        schema = load_execution_result_v1_schema()
        Draft202012Validator(schema).validate(document)
    except Exception:
        schema_failed = True
    if schema_failed:
        raise ExecutionResultSchemaError(
            "apply.invalid_result_schema",
            "execution result failed schema validation",
        )


def validate_result_document_semantics(document: dict[str, Any]) -> None:
    """Enforce stage provenance, counters, failure codes, and resultIdentity."""
    if document.get("apiVersion") != RESULT_API_VERSION:
        _integrity(
            "apply.invalid_result_version",
            "unsupported or missing execution-result apiVersion",
            path="/apiVersion",
        )

    status = document.get("status")
    mode = document.get("mode")
    if status not in FAILURE_CODES_BY_STATUS:
        _integrity("apply.invalid_result_status", "unknown execution status", path="/status")
    if mode not in {"dry-run", "apply"}:
        _integrity("apply.invalid_result_mode", "unknown execution mode", path="/mode")

    for field in (
        "planIdentity",
        "plannedTargetContextIdentity",
        "plannedRemoteStateIdentity",
        "resultIdentity",
    ):
        if not is_sha256_identity(document.get(field)):
            _integrity(
                "apply.invalid_result_identity",
                f"{field} hash format is invalid",
                path=f"/{field}",
            )

    execution_target = document.get("executionTargetContextIdentity")
    if execution_target is not None and not is_sha256_identity(execution_target):
        _integrity(
            "apply.invalid_result_identity",
            "executionTargetContextIdentity hash format is invalid",
            path="/executionTargetContextIdentity",
        )

    observed = document.get("observedRemoteStateIdentity")
    if observed is not None and not is_sha256_identity(observed):
        _integrity(
            "apply.invalid_result_identity",
            "observedRemoteStateIdentity hash format is invalid",
            path="/observedRemoteStateIdentity",
        )

    planned_target = document["plannedTargetContextIdentity"]
    planned_remote = document["plannedRemoteStateIdentity"]
    performed = document.get("writesPerformed")
    attempted = document.get("writesAttempted")
    unknown = document.get("writesUnknown")
    if not isinstance(performed, int) or performed < 0:
        _integrity(
            "apply.invalid_result_counters", "writesPerformed invalid", path="/writesPerformed"
        )
    if not isinstance(attempted, int) or attempted < 0:
        _integrity(
            "apply.invalid_result_counters", "writesAttempted invalid", path="/writesAttempted"
        )
    if not isinstance(unknown, int) or unknown < 0:
        _integrity("apply.invalid_result_counters", "writesUnknown invalid", path="/writesUnknown")
    if performed > attempted or unknown > attempted:
        _integrity(
            "apply.invalid_result_counters",
            "writesPerformed/writesUnknown must be <= writesAttempted",
        )

    operations = document.get("operations")
    if not isinstance(operations, list):
        _integrity(
            "apply.invalid_result_operations", "operations must be an array", path="/operations"
        )

    sequences = [op.get("sequence") for op in operations]
    if sequences != list(range(1, len(operations) + 1)):
        _integrity(
            "apply.invalid_result_operations",
            "operation sequences must be contiguous from 1",
            path="/operations",
        )

    succeeded = sum(1 for op in operations if op.get("status") == "succeeded")
    failed = sum(1 for op in operations if op.get("status") == "failed")
    unknowns = sum(1 for op in operations if op.get("status") == "unknown")
    if performed != succeeded:
        _integrity(
            "apply.invalid_result_counters",
            "writesPerformed must equal count of succeeded operations",
            path="/writesPerformed",
        )
    if unknown != unknowns:
        _integrity(
            "apply.invalid_result_counters",
            "writesUnknown must equal count of unknown operations",
            path="/writesUnknown",
        )

    _validate_operation_status_pattern(
        status=status,
        operations=operations,
        writes_performed=performed,
        writes_attempted=attempted,
        writes_unknown=unknown,
    )

    failure = document.get("failure")
    allowed = FAILURE_CODES_BY_STATUS[status]
    if allowed is None:
        if failure is not None:
            _integrity(
                "apply.invalid_result_failure",
                "success statuses require failure null",
                path="/failure",
            )
    else:
        if not isinstance(failure, dict) or failure.get("code") not in allowed:
            _integrity(
                "apply.invalid_result_failure",
                "failure.code is not allowed for this status",
                path="/failure/code",
            )

    # Stage provenance matrix.
    if status == "blocked":
        if mode not in {"dry-run", "apply"}:
            _integrity("apply.invalid_result_mode", "blocked requires valid mode", path="/mode")
        if execution_target is not None:
            _integrity(
                "apply.invalid_result_target",
                "blocked must not record execution target",
                path="/executionTargetContextIdentity",
            )
        if observed is not None:
            _integrity(
                "apply.invalid_result_remote",
                "blocked must not record observed remote identity",
                path="/observedRemoteStateIdentity",
            )
        if attempted != 0 or performed != 0 or unknown != 0:
            _integrity("apply.invalid_result_counters", "blocked requires zero counters")
        if any(op.get("status") != "not-run" for op in operations):
            _integrity("apply.invalid_result_operations", "blocked requires all operations not-run")

    elif status == "wrong-target":
        if execution_target is None:
            _integrity(
                "apply.invalid_result_target",
                "wrong-target requires executionTargetContextIdentity",
                path="/executionTargetContextIdentity",
            )
        if execution_target == planned_target:
            _integrity(
                "apply.invalid_result_target",
                "wrong-target requires mismatched target identities",
                path="/executionTargetContextIdentity",
            )
        if observed is not None:
            _integrity(
                "apply.invalid_result_remote",
                "wrong-target must not record observed remote identity",
                path="/observedRemoteStateIdentity",
            )
        if attempted != 0 or performed != 0 or unknown != 0:
            _integrity("apply.invalid_result_counters", "wrong-target requires zero counters")
        if any(op.get("status") != "not-run" for op in operations):
            _integrity(
                "apply.invalid_result_operations",
                "wrong-target requires all operations not-run",
            )

    elif status == "failed-before-write":
        if execution_target is None or execution_target != planned_target:
            _integrity(
                "apply.invalid_result_target",
                "failed-before-write requires matching execution target",
                path="/executionTargetContextIdentity",
            )
        if observed is not None:
            _integrity(
                "apply.invalid_result_remote",
                "failed-before-write must not record observed remote identity",
                path="/observedRemoteStateIdentity",
            )
        if attempted != 0 or performed != 0 or unknown != 0:
            _integrity(
                "apply.invalid_result_counters",
                "failed-before-write requires zero counters",
            )
        if any(op.get("status") != "not-run" for op in operations):
            _integrity(
                "apply.invalid_result_operations",
                "failed-before-write requires all operations not-run",
            )

    elif status == "stale":
        if execution_target is None or execution_target != planned_target:
            _integrity(
                "apply.invalid_result_target",
                "stale requires matching execution target",
                path="/executionTargetContextIdentity",
            )
        if observed is None:
            _integrity(
                "apply.invalid_result_remote",
                "stale requires observedRemoteStateIdentity",
                path="/observedRemoteStateIdentity",
            )
        if observed == planned_remote:
            _integrity(
                "apply.invalid_result_remote",
                "stale requires observed != planned remote identity",
                path="/observedRemoteStateIdentity",
            )
        if attempted != 0 or performed != 0 or unknown != 0:
            _integrity("apply.invalid_result_counters", "stale requires zero counters")
        if any(op.get("status") != "not-run" for op in operations):
            _integrity("apply.invalid_result_operations", "stale requires all operations not-run")

    elif status == "dry-run-ready":
        if mode != "dry-run":
            _integrity(
                "apply.invalid_result_mode", "dry-run-ready requires mode dry-run", path="/mode"
            )
        if execution_target is None or execution_target != planned_target:
            _integrity(
                "apply.invalid_result_target",
                "dry-run-ready requires matching execution target",
                path="/executionTargetContextIdentity",
            )
        if observed is None or observed != planned_remote:
            _integrity(
                "apply.invalid_result_remote",
                "dry-run-ready requires observed == planned remote identity",
                path="/observedRemoteStateIdentity",
            )
        if attempted != 0 or performed != 0 or unknown != 0:
            _integrity("apply.invalid_result_counters", "dry-run-ready requires zero counters")
        if any(op.get("status") != "not-run" for op in operations):
            _integrity(
                "apply.invalid_result_operations",
                "dry-run-ready requires all operations not-run",
            )

    elif status == "applied":
        if mode != "apply":
            _integrity("apply.invalid_result_mode", "applied requires mode apply", path="/mode")
        if execution_target is None or execution_target != planned_target:
            _integrity(
                "apply.invalid_result_target",
                "applied requires matching execution target",
                path="/executionTargetContextIdentity",
            )
        if observed is None or observed != planned_remote:
            _integrity(
                "apply.invalid_result_remote",
                "applied requires observed == planned remote identity",
                path="/observedRemoteStateIdentity",
            )
        if failed != 0 or unknowns != 0:
            _integrity(
                "apply.invalid_result_operations",
                "applied requires all operations succeeded",
            )
        if attempted != performed or performed != len(operations) or unknown != 0:
            _integrity(
                "apply.invalid_result_counters",
                "applied requires attempted=performed=operation count",
            )
        if any(op.get("status") != "succeeded" for op in operations):
            _integrity(
                "apply.invalid_result_operations",
                "applied requires all operations succeeded",
            )

    elif status == "write-failed":
        if mode != "apply":
            _integrity(
                "apply.invalid_result_mode", "write-failed requires mode apply", path="/mode"
            )
        if execution_target is None or execution_target != planned_target:
            _integrity(
                "apply.invalid_result_target",
                "write-failed requires matching execution target",
                path="/executionTargetContextIdentity",
            )
        if observed is None or observed != planned_remote:
            _integrity(
                "apply.invalid_result_remote",
                "write-failed requires observed == planned remote identity",
                path="/observedRemoteStateIdentity",
            )
        if failed != 1 or unknowns != 0:
            _integrity(
                "apply.invalid_result_operations",
                "write-failed requires exactly one failed and no unknown",
            )
        if attempted != performed + 1 or unknown != 0:
            _integrity(
                "apply.invalid_result_counters",
                "write-failed requires attempted=performed+1 and unknown=0",
            )

    elif status == "indeterminate":
        if mode != "apply":
            _integrity(
                "apply.invalid_result_mode", "indeterminate requires mode apply", path="/mode"
            )
        if execution_target is None or execution_target != planned_target:
            _integrity(
                "apply.invalid_result_target",
                "indeterminate requires matching execution target",
                path="/executionTargetContextIdentity",
            )
        if observed is None or observed != planned_remote:
            _integrity(
                "apply.invalid_result_remote",
                "indeterminate requires observed == planned remote identity",
                path="/observedRemoteStateIdentity",
            )
        if unknowns != 1 or failed != 0:
            _integrity(
                "apply.invalid_result_operations",
                "indeterminate requires exactly one unknown and no failed",
            )
        if attempted != performed + 1 or unknown != 1:
            _integrity(
                "apply.invalid_result_counters",
                "indeterminate requires attempted=performed+1 and unknown=1",
            )

    without_identity = dict(document)
    without_identity.pop("resultIdentity", None)
    expected_identity = compute_result_identity(without_identity)
    if document.get("resultIdentity") != expected_identity:
        _integrity(
            "apply.result_identity_mismatch",
            "resultIdentity does not match canonical document hash",
            path="/resultIdentity",
        )


def validate_result_document_for_serialization(document: dict[str, Any]) -> None:
    validate_result_document_schema(document)
    validate_result_document_semantics(document)


def dumps_result_canonical(document: dict[str, Any]) -> str:
    validate_result_document_for_serialization(document)
    return dumps_canonical(document)
