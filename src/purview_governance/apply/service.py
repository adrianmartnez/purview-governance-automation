"""Safe explicit Data Source apply workflow (dry-run default)."""

from __future__ import annotations

from purview_governance.apply.errors import ApplyValidationError
from purview_governance.apply.models import (
    ExecutionFailure,
    ExecutionMode,
    ExecutionResult,
    OperationResult,
    build_execution_result_from_parts,
)
from purview_governance.apply.payloads import MutationIntent, materialize_mutation_intents
from purview_governance.apply.validation import validate_result_document_for_serialization
from purview_governance.auth.errors import AuthenticationError
from purview_governance.config.normalize import normalize_endpoint
from purview_governance.plan.errors import PlanError
from purview_governance.plan.identity import PLAN_API_VERSION, compute_target_context_identity
from purview_governance.plan.models import GovernancePlan
from purview_governance.plan.validation import validate_plan_document_for_serialization
from purview_governance.remote_state.errors import RemoteStateError
from purview_governance.remote_state.service import capture_remote_state
from purview_governance.scanning.client import PurviewScanningClient
from purview_governance.scanning.errors import (
    PurviewClientError,
    PurviewHttpError,
    PurviewRequestError,
    PurviewTimeoutError,
)


def execute_governance_plan(
    plan: GovernancePlan,
    client: PurviewScanningClient,
    *,
    mode: ExecutionMode = ExecutionMode.DRY_RUN,
) -> ExecutionResult:
    """Execute a governance plan with fail-closed preflight and dry-run default.

    Public ``GovernancePlan`` objects are treated as untrusted and revalidated.
    Mutation requires ``mode=ExecutionMode.APPLY``.
    Apply supports ``purview-governance-plan/v1`` only; plan/v2 is rejected before network.
    """
    _revalidate_plan(plan)
    mode = _coerce_mode(mode)

    planned_target = plan.target_context.identity
    planned_remote = plan.identities.remote_state
    not_run_ops = _not_run_operations(plan)

    if plan.execution_eligibility == "blocked":
        return _finalize_result(
            plan_identity=plan.plan_identity,
            planned_target=planned_target,
            execution_target=None,
            planned_remote=planned_remote,
            observed_remote=None,
            mode=mode,
            status="blocked",
            writes_performed=0,
            writes_attempted=0,
            writes_unknown=0,
            operations=not_run_ops,
            failure=ExecutionFailure(code="apply.plan_blocked"),
        )

    for operation in plan.operations:
        if operation.action not in {"create", "replace"} or operation.resource_type != "dataSource":
            raise ApplyValidationError(
                "apply.payload_preflight_failed",
                "plan contains unsupported mutation operations",
            )

    execution_target = compute_target_context_identity(client.target_endpoint)
    plan_endpoint = normalize_endpoint(plan.target_context.endpoint)
    if plan_endpoint != client.target_endpoint or execution_target != planned_target:
        return _finalize_result(
            plan_identity=plan.plan_identity,
            planned_target=planned_target,
            execution_target=execution_target,
            planned_remote=planned_remote,
            observed_remote=None,
            mode=mode,
            status="wrong-target",
            writes_performed=0,
            writes_attempted=0,
            writes_unknown=0,
            operations=not_run_ops,
            failure=ExecutionFailure(code="apply.wrong_target"),
        )

    intents_failed = False
    intents: tuple[MutationIntent, ...] = ()
    try:
        intents = materialize_mutation_intents(plan)
    except ApplyValidationError:
        intents_failed = True
    if intents_failed:
        return _finalize_result(
            plan_identity=plan.plan_identity,
            planned_target=planned_target,
            execution_target=execution_target,
            planned_remote=planned_remote,
            observed_remote=None,
            mode=mode,
            status="failed-before-write",
            writes_performed=0,
            writes_attempted=0,
            writes_unknown=0,
            operations=not_run_ops,
            failure=ExecutionFailure(code="apply.payload_preflight_failed"),
        )

    capture_failed_code: str | None = None
    observed_remote: str | None = None
    try:
        remote_state = capture_remote_state(client)
        observed_remote = remote_state.material_state_identity
    except AuthenticationError:
        capture_failed_code = "apply.authentication_failed"
    except RemoteStateError:
        capture_failed_code = "apply.remote_state_failed"
    except PurviewClientError:
        capture_failed_code = "apply.remote_read_failed"
    except Exception:
        capture_failed_code = "apply.remote_read_failed"
    if capture_failed_code is not None:
        return _finalize_result(
            plan_identity=plan.plan_identity,
            planned_target=planned_target,
            execution_target=execution_target,
            planned_remote=planned_remote,
            observed_remote=None,
            mode=mode,
            status="failed-before-write",
            writes_performed=0,
            writes_attempted=0,
            writes_unknown=0,
            operations=not_run_ops,
            failure=ExecutionFailure(code=capture_failed_code),
        )

    assert observed_remote is not None
    if observed_remote != planned_remote:
        return _finalize_result(
            plan_identity=plan.plan_identity,
            planned_target=planned_target,
            execution_target=execution_target,
            planned_remote=planned_remote,
            observed_remote=observed_remote,
            mode=mode,
            status="stale",
            writes_performed=0,
            writes_attempted=0,
            writes_unknown=0,
            operations=not_run_ops,
            failure=ExecutionFailure(code="apply.stale_plan"),
        )

    if mode is ExecutionMode.DRY_RUN:
        return _finalize_result(
            plan_identity=plan.plan_identity,
            planned_target=planned_target,
            execution_target=execution_target,
            planned_remote=planned_remote,
            observed_remote=observed_remote,
            mode=mode,
            status="dry-run-ready",
            writes_performed=0,
            writes_attempted=0,
            writes_unknown=0,
            operations=not_run_ops,
            failure=None,
        )

    return _apply_intents(
        plan=plan,
        client=client,
        intents=intents,
        planned_target=planned_target,
        execution_target=execution_target,
        planned_remote=planned_remote,
        observed_remote=observed_remote,
    )


def _revalidate_plan(plan: object) -> None:
    if not isinstance(plan, GovernancePlan):
        raise ApplyValidationError(
            "apply.invalid_plan",
            "plan must be a GovernancePlan instance",
        )
    if plan.api_version != PLAN_API_VERSION:
        raise ApplyValidationError(
            "apply.unsupported_plan_version",
            "apply supports purview-governance-plan/v1 only",
        )
    failed = False
    try:
        document = plan.to_document()
        if document.get("apiVersion") != PLAN_API_VERSION:
            raise ApplyValidationError(
                "apply.unsupported_plan_version",
                "apply supports purview-governance-plan/v1 only",
            )
        validate_plan_document_for_serialization(document)
    except ApplyValidationError:
        raise
    except PlanError:
        failed = True
    except Exception:
        failed = True
    if failed:
        raise ApplyValidationError(
            "apply.invalid_plan",
            "plan failed schema or semantic integrity validation",
        )


def _coerce_mode(mode: object) -> ExecutionMode:
    if isinstance(mode, ExecutionMode):
        return mode
    raise ApplyValidationError(
        "apply.invalid_mode",
        "execution mode must be ExecutionMode.DRY_RUN or ExecutionMode.APPLY",
    )


def _not_run_operations(plan: GovernancePlan) -> tuple[OperationResult, ...]:
    return tuple(
        OperationResult(
            sequence=operation.sequence,
            resource_type="dataSource",
            name=operation.name,
            action=operation.action,
            status="not-run",
        )
        for operation in plan.operations
    )


def _apply_intents(
    *,
    plan: GovernancePlan,
    client: PurviewScanningClient,
    intents: tuple[MutationIntent, ...],
    planned_target: str,
    execution_target: str,
    planned_remote: str,
    observed_remote: str,
) -> ExecutionResult:
    op_results: list[OperationResult] = [
        OperationResult(
            sequence=intent.sequence,
            resource_type="dataSource",
            name=intent.name,
            action=intent.action,
            status="not-run",
        )
        for intent in intents
    ]
    performed = 0
    attempted = 0
    unknown = 0

    for index, intent in enumerate(intents):
        attempted += 1
        outcome = _invoke_put(client, intent)
        if outcome == "succeeded":
            performed += 1
            op_results[index] = OperationResult(
                sequence=intent.sequence,
                resource_type="dataSource",
                name=intent.name,
                action=intent.action,
                status="succeeded",
            )
            continue
        if outcome == "failed_auth":
            op_results[index] = OperationResult(
                sequence=intent.sequence,
                resource_type="dataSource",
                name=intent.name,
                action=intent.action,
                status="failed",
            )
            return _finalize_result(
                plan_identity=plan.plan_identity,
                planned_target=planned_target,
                execution_target=execution_target,
                planned_remote=planned_remote,
                observed_remote=observed_remote,
                mode=ExecutionMode.APPLY,
                status="write-failed",
                writes_performed=performed,
                writes_attempted=attempted,
                writes_unknown=0,
                operations=tuple(op_results),
                failure=ExecutionFailure(code="apply.write_auth_failed"),
            )
        if outcome == "failed_rejected":
            op_results[index] = OperationResult(
                sequence=intent.sequence,
                resource_type="dataSource",
                name=intent.name,
                action=intent.action,
                status="failed",
            )
            return _finalize_result(
                plan_identity=plan.plan_identity,
                planned_target=planned_target,
                execution_target=execution_target,
                planned_remote=planned_remote,
                observed_remote=observed_remote,
                mode=ExecutionMode.APPLY,
                status="write-failed",
                writes_performed=performed,
                writes_attempted=attempted,
                writes_unknown=0,
                operations=tuple(op_results),
                failure=ExecutionFailure(code="apply.write_rejected"),
            )
        # unknown / indeterminate
        unknown = 1
        op_results[index] = OperationResult(
            sequence=intent.sequence,
            resource_type="dataSource",
            name=intent.name,
            action=intent.action,
            status="unknown",
        )
        return _finalize_result(
            plan_identity=plan.plan_identity,
            planned_target=planned_target,
            execution_target=execution_target,
            planned_remote=planned_remote,
            observed_remote=observed_remote,
            mode=ExecutionMode.APPLY,
            status="indeterminate",
            writes_performed=performed,
            writes_attempted=attempted,
            writes_unknown=unknown,
            operations=tuple(op_results),
            failure=ExecutionFailure(code="apply.write_outcome_unknown"),
        )

    return _finalize_result(
        plan_identity=plan.plan_identity,
        planned_target=planned_target,
        execution_target=execution_target,
        planned_remote=planned_remote,
        observed_remote=observed_remote,
        mode=ExecutionMode.APPLY,
        status="applied",
        writes_performed=performed,
        writes_attempted=attempted,
        writes_unknown=0,
        operations=tuple(op_results),
        failure=None,
    )


def _invoke_put(client: PurviewScanningClient, intent: MutationIntent) -> str:
    """Invoke the package-private PUT primitive and classify the outcome."""
    try:
        receipt = client._create_or_replace_data_source(intent.name, intent.payload)
    except AuthenticationError:
        return "failed_auth"
    except PurviewHttpError as exc:
        if 400 <= exc.status_code <= 499:
            return "failed_rejected"
        return "unknown"
    except (PurviewTimeoutError, PurviewRequestError):
        return "unknown"
    except PurviewClientError:
        return "unknown"
    except Exception:
        return "unknown"
    if receipt.status_code in {200, 201}:
        return "succeeded"
    return "unknown"


def _finalize_result(
    *,
    plan_identity: str,
    planned_target: str,
    execution_target: str | None,
    planned_remote: str,
    observed_remote: str | None,
    mode: ExecutionMode,
    status: str,
    writes_performed: int,
    writes_attempted: int,
    writes_unknown: int,
    operations: tuple[OperationResult, ...],
    failure: ExecutionFailure | None,
) -> ExecutionResult:
    result = build_execution_result_from_parts(
        plan_identity=plan_identity,
        planned_target_context_identity=planned_target,
        execution_target_context_identity=execution_target,
        planned_remote_state_identity=planned_remote,
        observed_remote_state_identity=observed_remote,
        mode=mode,
        status=status,  # type: ignore[arg-type]
        writes_performed=writes_performed,
        writes_attempted=writes_attempted,
        writes_unknown=writes_unknown,
        operations=operations,
        failure=failure,
    )
    validate_result_document_for_serialization(result.to_document())
    return result
