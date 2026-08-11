"""Deterministic human-inspectable execution-result summary."""

from __future__ import annotations

from purview_governance.apply.models import ExecutionResult
from purview_governance.apply.models_v2 import ExecutionResultV2, OperationResultV2


def format_execution_result_summary(result: ExecutionResult | ExecutionResultV2) -> str:
    """Return a deterministic plain-text summary (no ANSI/timestamps/secrets)."""
    failure_code = "null" if result.failure is None else result.failure.code
    lines: list[str] = [
        f"apiVersion: {result.api_version}",
        f"status: {result.status}",
        f"mode: {result.mode.value}",
        f"resultIdentity: {result.result_identity}",
        f"planIdentity: {result.plan_identity}",
        f"plannedTargetContextIdentity: {result.planned_target_context_identity}",
        f"executionTargetContextIdentity: {result.execution_target_context_identity}",
        f"plannedRemoteStateIdentity: {result.planned_remote_state_identity}",
        f"observedRemoteStateIdentity: {result.observed_remote_state_identity}",
        f"writesPerformed: {result.writes_performed}",
        f"writesAttempted: {result.writes_attempted}",
        f"writesUnknown: {result.writes_unknown}",
        f"failure.code: {failure_code}",
        "operations:",
    ]
    if not result.operations:
        lines.append("  (none)")
    else:
        for operation in result.operations:
            identity = f"{operation.resource_type}/{operation.name}"
            if isinstance(operation, OperationResultV2) and operation.resource_type == "scan":
                identity = (
                    f"{operation.resource_type}/{operation.data_source_name}/{operation.name}"
                )
            lines.append(
                f"  {operation.sequence}. {operation.action} {identity} status={operation.status}"
            )
    return "\n".join(lines) + "\n"
