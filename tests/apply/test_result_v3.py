"""execution-result/v3 roundtrip and partial invariants."""

from __future__ import annotations

import pytest

from purview_governance.apply import (
    ExecutionMode,
    OperationResultV3,
    build_execution_result_v3_from_parts,
    load_execution_result_text,
)
from purview_governance.apply.errors import ExecutionResultIntegrityError
from purview_governance.apply.identity import RESULT_API_VERSION_V3
from purview_governance.apply.validation_v3 import validate_result_document_v3_for_serialization


def test_partial_status_roundtrip() -> None:
    h = "sha256:" + ("a" * 64)
    ops = (
        OperationResultV3(
            sequence=1,
            resource_type="glossaryTerm",
            resource_id="50000000-0000-4000-8000-000000000001",
            action="create",
            status="succeeded",
        ),
        OperationResultV3(
            sequence=2,
            resource_type="glossaryTerm",
            resource_id="50000000-0000-4000-8000-000000000002",
            action="create",
            status="not-run",
        ),
    )
    result = build_execution_result_v3_from_parts(
        plan_identity=h,
        planned_target_context_identity=h,
        execution_target_context_identity=h,
        planned_remote_state_identity=h,
        observed_remote_state_identity=h,
        mode=ExecutionMode.APPLY,
        status="partial",
        writes_performed=1,
        writes_attempted=1,
        writes_unknown=0,
        operations=ops,
        failure=__import__(
            "purview_governance.apply.models", fromlist=["ExecutionFailure"]
        ).ExecutionFailure(code="apply.pre_write_stale_after_writes"),
    )
    assert result.api_version == RESULT_API_VERSION_V3
    canonical = result.to_canonical_json()
    loaded = load_execution_result_text(canonical)
    assert loaded.status == "partial"
    assert loaded.operations[0].status == "succeeded"
    assert loaded.operations[1].status == "not-run"


def test_result_identity_tamper_detected() -> None:
    h = "sha256:" + ("b" * 64)
    result = build_execution_result_v3_from_parts(
        plan_identity=h,
        planned_target_context_identity=h,
        execution_target_context_identity=h,
        planned_remote_state_identity=h,
        observed_remote_state_identity=h,
        mode=ExecutionMode.DRY_RUN,
        status="dry-run-ready",
        writes_performed=0,
        writes_attempted=0,
        writes_unknown=0,
        operations=(),
        failure=None,
    )
    doc = result.to_document()
    doc["resultIdentity"] = "sha256:" + ("c" * 64)
    with pytest.raises(ExecutionResultIntegrityError):
        validate_result_document_v3_for_serialization(doc)
