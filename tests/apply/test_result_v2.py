"""execution-result/v2 identity and scan parent fields."""

from __future__ import annotations

import pytest

from purview_governance.apply import (
    ExecutionMode,
    OperationResultV2,
    build_execution_result_v2_from_parts,
    load_execution_result_text,
)
from purview_governance.apply.errors import ExecutionResultIntegrityError
from purview_governance.apply.identity import RESULT_API_VERSION_V2
from purview_governance.apply.validation_v2 import validate_result_document_v2_for_serialization


def test_dual_daily_scan_operations_unambiguous() -> None:
    h = "sha256:" + ("d" * 64)
    ops = (
        OperationResultV2(
            sequence=1,
            resource_type="scan",
            name="DailyScan",
            action="create",
            status="not-run",
            data_source_name="ds-a",
        ),
        OperationResultV2(
            sequence=2,
            resource_type="scan",
            name="DailyScan",
            action="create",
            status="not-run",
            data_source_name="ds-b",
        ),
    )
    result = build_execution_result_v2_from_parts(
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
        operations=ops,
        failure=None,
    )
    assert result.api_version == RESULT_API_VERSION_V2
    canonical = result.to_canonical_json()
    loaded = load_execution_result_text(canonical)
    assert {(op.data_source_name, op.name) for op in loaded.operations} == {
        ("ds-a", "DailyScan"),
        ("ds-b", "DailyScan"),
    }


def test_result_identity_tamper_detected() -> None:
    h = "sha256:" + ("e" * 64)
    result = build_execution_result_v2_from_parts(
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
    doc["resultIdentity"] = "sha256:" + ("f" * 64)
    with pytest.raises(ExecutionResultIntegrityError) as exc:
        validate_result_document_v2_for_serialization(doc)
    assert exc.value.code == "apply.result_identity_mismatch"
