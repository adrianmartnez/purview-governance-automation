"""Packaged execution-result/v3 schema regression (editable install)."""

from __future__ import annotations

import json

from purview_governance.apply import (
    ExecutionMode,
    OperationResultV3,
    build_execution_result_v3_from_parts,
    load_execution_result_text,
    load_execution_result_v3_schema,
)


def test_execution_result_v3_packaged_roundtrip() -> None:
    schema = load_execution_result_v3_schema()
    assert schema["$id"].endswith("/purview-execution-result/v3")
    h = "sha256:" + ("d" * 64)
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
        operations=(
            OperationResultV3(
                sequence=1,
                resource_type="dataProduct",
                resource_id="40000000-0000-4000-8000-000000000001",
                action="create",
                status="not-run",
            ),
        ),
        failure=None,
    )
    canonical = result.to_canonical_json()
    loaded = load_execution_result_text(canonical)
    assert loaded.to_canonical_json() == canonical
    pretty = json.dumps(json.loads(canonical), indent=2, ensure_ascii=False)
    loaded_pretty = load_execution_result_text(pretty)
    assert loaded_pretty.to_canonical_json() == canonical
