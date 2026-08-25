"""Controlled apply workflow for plan/v3 against Unified Catalog."""

from __future__ import annotations

import json

from purview_governance.apply.errors import ApplyValidationError
from purview_governance.apply.models import ExecutionFailure, ExecutionMode
from purview_governance.apply.models_v3 import (
    ExecutionResultV3,
    OperationResultV3,
    build_execution_result_v3_from_parts,
)
from purview_governance.apply.payloads_v3 import (
    FAILURE_PREFLIGHT,
    MutationIntentV3,
    OperationPreflightRecord,
    PreflightContext,
    VirtualExecutionStateV3,
    bind_deferred_value_identities,
    build_fresh_deferred_index,
    check_plan_dependencies,
    deferred_identities_from_raw,
    materialize_mutation_intents_v3,
    simulate_virtual_state,
    validate_operation_capability,
)
from purview_governance.apply.validation_v3 import validate_result_document_v3_for_serialization
from purview_governance.auth.errors import AuthenticationError
from purview_governance.auth.tenant_bound import TenantBindingUnsupportedError
from purview_governance.plan.errors import PlanError
from purview_governance.plan.identity import PLAN_API_VERSION_V3
from purview_governance.plan.models_v3 import GovernancePlanV3, PlanOperationV3
from purview_governance.plan.validation_v3 import (
    validate_plan_document_for_serialization_v3,
    validate_remote_state_for_planning_v3,
)
from purview_governance.remote_state.capture_recipe import derive_capture_recipe
from purview_governance.remote_state.errors import RemoteStateError
from purview_governance.remote_state.models_v3 import RemoteStateV3
from purview_governance.remote_state.service import capture_unified_catalog_remote_state_v3
from purview_governance.unified_catalog.client import PurviewUnifiedCatalogClient
from purview_governance.unified_catalog.errors import (
    UnifiedCatalogClientError,
    UnifiedCatalogHttpError,
    UnifiedCatalogRequestError,
    UnifiedCatalogResponseError,
    UnifiedCatalogTimeoutError,
)


def execute_governance_plan_v3(
    plan: GovernancePlanV3,
    planned_remote_state: RemoteStateV3,
    client: PurviewUnifiedCatalogClient,
    *,
    mode: ExecutionMode = ExecutionMode.DRY_RUN,
) -> ExecutionResultV3:
    """Execute a governance plan/v3 with fail-closed preflight and dry-run default."""
    if not isinstance(plan, GovernancePlanV3):
        raise ApplyValidationError(
            "apply.invalid_plan",
            "plan must be a GovernancePlanV3 instance",
        )
    if not isinstance(planned_remote_state, RemoteStateV3):
        raise ApplyValidationError(
            "apply.invalid_remote_state",
            "planned_remote_state must be a RemoteStateV3 instance",
        )

    _revalidate_plan_v3(plan)
    mode = _coerce_mode(mode)

    planned_target = plan.target_context.identity
    planned_remote = plan.identities.remote_state
    not_run_ops = _not_run_operations_v3(plan)

    if plan.execution_eligibility == "blocked":
        return _finalize_result_v3(
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

    try:
        validate_remote_state_for_planning_v3(planned_remote_state)
    except RemoteStateError:
        return _failed_before_write_v3(
            plan=plan,
            planned_target=planned_target,
            planned_remote=planned_remote,
            mode=mode,
            operations=not_run_ops,
            code="apply.invalid_remote_state",
        )

    if planned_remote_state.material_state_identity != planned_remote:
        return _failed_before_write_v3(
            plan=plan,
            planned_target=planned_target,
            planned_remote=planned_remote,
            mode=mode,
            operations=not_run_ops,
            code="apply.remote_state_identity_mismatch",
        )

    if planned_remote_state.target_context.identity != planned_target:
        return _failed_before_write_v3(
            plan=plan,
            planned_target=planned_target,
            planned_remote=planned_remote,
            mode=mode,
            operations=not_run_ops,
            code="apply.remote_state_identity_mismatch",
        )

    try:
        execution_context = client._require_tenant_bound_execution_context()
    except TenantBindingUnsupportedError as exc:
        return _failed_before_write_v3(
            plan=plan,
            planned_target=planned_target,
            planned_remote=planned_remote,
            mode=mode,
            operations=not_run_ops,
            code=exc.code,
        )

    execution_target = execution_context.execution_target_context_identity
    if execution_target != planned_target:
        return _finalize_result_v3(
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

    try:
        recipe = derive_capture_recipe(planned_remote_state)
    except RemoteStateError:
        return _failed_before_write_v3(
            plan=plan,
            planned_target=planned_target,
            planned_remote=planned_remote,
            mode=mode,
            operations=not_run_ops,
            execution_target=execution_target,
            code="apply.remote_state_failed",
        )

    capture_failed_code: str | None = None
    observed_remote: str | None = None
    fresh_remote: RemoteStateV3 | None = None
    try:
        fresh_remote = capture_unified_catalog_remote_state_v3(
            client,
            tenant_id=execution_context.execution_tenant_id,
            include_data_products=recipe.include_data_products,
            include_glossary_terms=recipe.include_glossary_terms,
            include_data_assets=recipe.include_data_assets,
            include_data_columns=recipe.include_data_columns,
            include_relationship_data_product_to_data_asset=recipe.include_relationship_data_product_to_data_asset,
            include_relationship_glossary_term_to_data_asset=recipe.include_relationship_glossary_term_to_data_asset,
            include_relationship_glossary_term_to_data_column=recipe.include_relationship_glossary_term_to_data_column,
        )
        observed_remote = fresh_remote.material_state_identity
    except AuthenticationError:
        capture_failed_code = "apply.authentication_failed"
    except TenantBindingUnsupportedError as exc:
        capture_failed_code = exc.code
    except RemoteStateError:
        capture_failed_code = "apply.remote_state_failed"
    except UnifiedCatalogClientError:
        capture_failed_code = "apply.remote_read_failed"
    except Exception:
        capture_failed_code = "apply.remote_read_failed"

    if capture_failed_code is not None:
        return _failed_before_write_v3(
            plan=plan,
            planned_target=planned_target,
            planned_remote=planned_remote,
            mode=mode,
            operations=not_run_ops,
            execution_target=execution_target,
            code=capture_failed_code,
        )

    assert fresh_remote is not None
    assert observed_remote is not None

    if observed_remote != planned_remote:
        return _finalize_result_v3(
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

    fresh_index = build_fresh_deferred_index(fresh_remote)
    virtual_state = VirtualExecutionStateV3.from_fresh_remote(fresh_remote)

    preflight_failed_code: str | None = None
    preflight_records: dict[int, OperationPreflightRecord] = {}
    rolling_virtual = virtual_state

    for operation in sorted(plan.operations, key=lambda item: item.sequence):
        capability_code = validate_operation_capability(
            operation,
            plan,
            fresh_remote,
            rolling_virtual,
        )
        if capability_code is not None:
            preflight_failed_code = capability_code
            break

        read_outcome = _targeted_get_for_operation(client, operation, rolling_virtual)
        if read_outcome.kind == "auth_failed":
            preflight_failed_code = "apply.authentication_failed"
            break
        if read_outcome.kind == "read_failed":
            preflight_failed_code = "apply.remote_read_failed"
            break
        if read_outcome.kind == "create_exists":
            preflight_failed_code = FAILURE_PREFLIGHT
            break
        if read_outcome.kind == "replace_missing":
            preflight_failed_code = FAILURE_PREFLIGHT
            break

        if operation.action == "replace":
            assert read_outcome.raw_get is not None
            if not bind_deferred_value_identities(
                read_outcome.raw_get,
                fresh_index,
                operation.resource_type,
            ):
                preflight_failed_code = FAILURE_PREFLIGHT
                break
            preflight_records[operation.sequence] = OperationPreflightRecord(
                raw_get=read_outcome.raw_get,
                deferred_fingerprints=deferred_identities_from_raw(
                    read_outcome.raw_get,
                    operation.resource_type,
                ),
            )

        if operation.action == "create":
            rolling_virtual = rolling_virtual.with_create(operation.resource_type, operation.id)

    if preflight_failed_code is None:
        dependency_code = check_plan_dependencies(plan, simulate_virtual_state(plan, fresh_remote))
        if dependency_code is not None:
            preflight_failed_code = dependency_code

    if preflight_failed_code is None:
        try:
            preflight_context = PreflightContext(
                plan=plan,
                fresh_deferred_index=fresh_index,
                by_sequence=preflight_records,
            )
            materialize_mutation_intents_v3(plan, preflight_context)
        except ApplyValidationError as exc:
            preflight_failed_code = exc.code

    if preflight_failed_code is not None:
        return _failed_before_write_v3(
            plan=plan,
            planned_target=planned_target,
            planned_remote=planned_remote,
            mode=mode,
            operations=not_run_ops,
            execution_target=execution_target,
            code=preflight_failed_code,
        )

    preflight_context = PreflightContext(
        plan=plan,
        fresh_deferred_index=fresh_index,
        by_sequence=preflight_records,
    )
    intents = materialize_mutation_intents_v3(plan, preflight_context)

    if mode is ExecutionMode.DRY_RUN:
        return _finalize_result_v3(
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

    return _apply_intents_v3(
        plan=plan,
        client=client,
        intents=intents,
        preflight_context=preflight_context,
        fresh_index=fresh_index,
        virtual_state=virtual_state,
        planned_target=planned_target,
        execution_target=execution_target,
        planned_remote=planned_remote,
        observed_remote=observed_remote,
    )


def _revalidate_plan_v3(plan: GovernancePlanV3) -> None:
    if plan.api_version != PLAN_API_VERSION_V3:
        raise ApplyValidationError(
            "apply.unsupported_plan_version",
            "apply supports purview-governance-plan/v3 only on this path",
        )
    failed = False
    try:
        validate_plan_document_for_serialization_v3(plan.to_document())
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


def _not_run_operations_v3(plan: GovernancePlanV3) -> tuple[OperationResultV3, ...]:
    return tuple(
        OperationResultV3(
            sequence=operation.sequence,
            resource_type=operation.resource_type,
            resource_id=operation.id,
            action=operation.action,
            status="not-run",
        )
        for operation in plan.operations
    )


def _failed_before_write_v3(
    *,
    plan: GovernancePlanV3,
    planned_target: str,
    planned_remote: str,
    mode: ExecutionMode,
    operations: tuple[OperationResultV3, ...],
    code: str,
    execution_target: str | None = None,
    observed_remote: str | None = None,
) -> ExecutionResultV3:
    return _finalize_result_v3(
        plan_identity=plan.plan_identity,
        planned_target=planned_target,
        execution_target=execution_target,
        planned_remote=planned_remote,
        observed_remote=observed_remote,
        mode=mode,
        status="failed-before-write",
        writes_performed=0,
        writes_attempted=0,
        writes_unknown=0,
        operations=operations,
        failure=ExecutionFailure(code=code),
    )


class _TargetedGetOutcome:
    __slots__ = ("kind", "raw_get")

    def __init__(self, kind: str, raw_get: dict | None = None) -> None:
        self.kind = kind
        self.raw_get = raw_get


def _targeted_get_for_operation(
    client: PurviewUnifiedCatalogClient,
    operation: PlanOperationV3,
    virtual_state: VirtualExecutionStateV3,
) -> _TargetedGetOutcome:
    try:
        if operation.resource_type == "businessDomain":
            raw = client.get_business_domain(operation.id)
        elif operation.resource_type == "dataProduct":
            raw = client.get_data_product(operation.id)
        else:
            raw = client.get_glossary_term(operation.id)
    except AuthenticationError:
        return _TargetedGetOutcome("auth_failed")
    except UnifiedCatalogHttpError as exc:
        if operation.action == "create" and exc.status_code == 404:
            return _TargetedGetOutcome("create_ok")
        if operation.action == "replace" and exc.status_code == 404:
            return _TargetedGetOutcome("replace_missing")
        if exc.status_code in {401, 403}:
            return _TargetedGetOutcome("auth_failed")
        return _TargetedGetOutcome("read_failed")
    except (UnifiedCatalogTimeoutError, UnifiedCatalogRequestError, UnifiedCatalogResponseError):
        return _TargetedGetOutcome("read_failed")
    except UnifiedCatalogClientError:
        return _TargetedGetOutcome("read_failed")
    except Exception:
        return _TargetedGetOutcome("read_failed")

    if operation.action == "create":
        return _TargetedGetOutcome("create_exists")
    return _TargetedGetOutcome("replace_ok", raw_get=raw)


def _apply_intents_v3(
    *,
    plan: GovernancePlanV3,
    client: PurviewUnifiedCatalogClient,
    intents: tuple[MutationIntentV3, ...],
    preflight_context: PreflightContext,
    fresh_index: dict,
    virtual_state: VirtualExecutionStateV3,
    planned_target: str,
    execution_target: str,
    planned_remote: str,
    observed_remote: str,
) -> ExecutionResultV3:
    op_results: list[OperationResultV3] = [
        OperationResultV3(
            sequence=intent.sequence,
            resource_type=intent.resource_type,
            resource_id=intent.resource_id,
            action=intent.action,
            status="not-run",
        )
        for intent in intents
    ]
    performed = 0
    rolling_virtual = virtual_state

    for index, intent in enumerate(intents):
        second_read = _second_pre_write_check(
            client,
            intent,
            preflight_context.by_sequence.get(intent.sequence),
            fresh_index,
            rolling_virtual,
        )
        if second_read is not None:
            if performed > 0:
                return _finalize_result_v3(
                    plan_identity=plan.plan_identity,
                    planned_target=planned_target,
                    execution_target=execution_target,
                    planned_remote=planned_remote,
                    observed_remote=observed_remote,
                    mode=ExecutionMode.APPLY,
                    status="partial",
                    writes_performed=performed,
                    writes_attempted=performed,
                    writes_unknown=0,
                    operations=tuple(op_results),
                    failure=ExecutionFailure(code=second_read),
                )
            return _finalize_result_v3(
                plan_identity=plan.plan_identity,
                planned_target=planned_target,
                execution_target=execution_target,
                planned_remote=planned_remote,
                observed_remote=None,
                mode=ExecutionMode.APPLY,
                status="failed-before-write",
                writes_performed=0,
                writes_attempted=0,
                writes_unknown=0,
                operations=tuple(op_results),
                failure=ExecutionFailure(code=_pre_first_write_failure_code(second_read)),
            )

        attempted = performed + 1
        write_outcome = _invoke_write_v3(client, intent)
        if write_outcome == "succeeded":
            verify_outcome = _post_write_verify_v3(client, intent)
            if verify_outcome != "succeeded":
                op_results[index] = OperationResultV3(
                    sequence=intent.sequence,
                    resource_type=intent.resource_type,
                    resource_id=intent.resource_id,
                    action=intent.action,
                    status="unknown",
                )
                return _finalize_result_v3(
                    plan_identity=plan.plan_identity,
                    planned_target=planned_target,
                    execution_target=execution_target,
                    planned_remote=planned_remote,
                    observed_remote=observed_remote,
                    mode=ExecutionMode.APPLY,
                    status="indeterminate",
                    writes_performed=performed,
                    writes_attempted=attempted,
                    writes_unknown=1,
                    operations=tuple(op_results),
                    failure=ExecutionFailure(code="apply.write_outcome_unknown"),
                )
            performed += 1
            op_results[index] = OperationResultV3(
                sequence=intent.sequence,
                resource_type=intent.resource_type,
                resource_id=intent.resource_id,
                action=intent.action,
                status="succeeded",
            )
            if intent.action == "create":
                rolling_virtual = rolling_virtual.with_create(
                    intent.resource_type,
                    intent.resource_id,
                )
            continue
        if write_outcome == "failed_auth":
            op_results[index] = OperationResultV3(
                sequence=intent.sequence,
                resource_type=intent.resource_type,
                resource_id=intent.resource_id,
                action=intent.action,
                status="failed",
            )
            return _finalize_result_v3(
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
        if write_outcome == "failed_rejected":
            op_results[index] = OperationResultV3(
                sequence=intent.sequence,
                resource_type=intent.resource_type,
                resource_id=intent.resource_id,
                action=intent.action,
                status="failed",
            )
            return _finalize_result_v3(
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
        op_results[index] = OperationResultV3(
            sequence=intent.sequence,
            resource_type=intent.resource_type,
            resource_id=intent.resource_id,
            action=intent.action,
            status="unknown",
        )
        return _finalize_result_v3(
            plan_identity=plan.plan_identity,
            planned_target=planned_target,
            execution_target=execution_target,
            planned_remote=planned_remote,
            observed_remote=observed_remote,
            mode=ExecutionMode.APPLY,
            status="indeterminate",
            writes_performed=performed,
            writes_attempted=attempted,
            writes_unknown=1,
            operations=tuple(op_results),
            failure=ExecutionFailure(code="apply.write_outcome_unknown"),
        )

    return _finalize_result_v3(
        plan_identity=plan.plan_identity,
        planned_target=planned_target,
        execution_target=execution_target,
        planned_remote=planned_remote,
        observed_remote=observed_remote,
        mode=ExecutionMode.APPLY,
        status="applied",
        writes_performed=performed,
        writes_attempted=performed,
        writes_unknown=0,
        operations=tuple(op_results),
        failure=None,
    )


def _second_pre_write_check(
    client: PurviewUnifiedCatalogClient,
    intent: MutationIntentV3,
    preflight_record: OperationPreflightRecord | None,
    fresh_index: dict,
    virtual_state: VirtualExecutionStateV3,
) -> str | None:
    operation = PlanOperationV3(
        sequence=intent.sequence,
        resource_type=intent.resource_type,
        id=intent.resource_id,
        action=intent.action,
    )
    read_outcome = _targeted_get_for_operation(client, operation, virtual_state)
    if read_outcome.kind == "auth_failed":
        return "apply.pre_write_auth_failed_after_writes"
    if read_outcome.kind in {"read_failed", "replace_missing", "create_exists"}:
        if read_outcome.kind == "replace_missing" or read_outcome.kind == "create_exists":
            return "apply.pre_write_stale_after_writes"
        return "apply.pre_write_read_failed_after_writes"

    if intent.action == "replace":
        assert read_outcome.raw_get is not None
        assert preflight_record is not None
        if not bind_deferred_value_identities(
            read_outcome.raw_get,
            fresh_index,
            intent.resource_type,
        ):
            return "apply.pre_write_stale_after_writes"
        fresh_fingerprints = deferred_identities_from_raw(
            read_outcome.raw_get,
            intent.resource_type,
        )
        if fresh_fingerprints != preflight_record.deferred_fingerprints:
            return "apply.pre_write_stale_after_writes"
        if json.dumps(read_outcome.raw_get, sort_keys=True) != json.dumps(
            preflight_record.raw_get,
            sort_keys=True,
        ):
            managed_drift = _managed_fields_drift(
                intent,
                preflight_record.raw_get,
                read_outcome.raw_get,
            )
            if managed_drift:
                return "apply.pre_write_stale_after_writes"
    return None


def _pre_first_write_failure_code(after_writes_code: str) -> str:
    """Map second-TOCTOU codes to pre-first-write failure taxonomy."""
    if after_writes_code == "apply.pre_write_stale_after_writes":
        return "apply.payload_preflight_failed"
    if after_writes_code == "apply.pre_write_auth_failed_after_writes":
        return "apply.authentication_failed"
    if after_writes_code == "apply.pre_write_read_failed_after_writes":
        return "apply.remote_read_failed"
    return after_writes_code


def _post_write_verify_v3(client: PurviewUnifiedCatalogClient, intent: MutationIntentV3) -> str:
    """Confirm resource exists after a successful write (GET verification)."""
    try:
        if intent.resource_type == "businessDomain":
            raw = client.get_business_domain(intent.resource_id)
        elif intent.resource_type == "dataProduct":
            raw = client.get_data_product(intent.resource_id)
        else:
            raw = client.get_glossary_term(intent.resource_id)
    except AuthenticationError:
        return "unknown"
    except UnifiedCatalogHttpError:
        return "unknown"
    except (UnifiedCatalogTimeoutError, UnifiedCatalogRequestError):
        return "unknown"
    except UnifiedCatalogResponseError:
        return "unknown"
    except UnifiedCatalogClientError:
        return "unknown"
    except Exception:
        return "unknown"
    resource_id = raw.get("id")
    if resource_id != intent.resource_id:
        return "unknown"
    return "succeeded"


def _managed_fields_drift(
    intent: MutationIntentV3,
    before: dict,
    after: dict,
) -> bool:
    keys = ("name", "description", "status", "domain", "parentId", "type")
    return any(before.get(key) != after.get(key) for key in keys)


def _invoke_write_v3(client: PurviewUnifiedCatalogClient, intent: MutationIntentV3) -> str:
    try:
        if intent.resource_type == "businessDomain":
            client._update_business_domain(intent.resource_id, intent.payload)
        elif intent.resource_type == "dataProduct":
            if intent.action == "create":
                client._create_data_product(intent.payload)
            else:
                client._update_data_product(intent.resource_id, intent.payload)
        elif intent.action == "create":
            client._create_glossary_term(intent.payload)
        else:
            client._update_glossary_term(intent.resource_id, intent.payload)
    except AuthenticationError:
        return "failed_auth"
    except UnifiedCatalogHttpError as exc:
        if exc.status_code in {401, 403}:
            return "failed_auth"
        if 400 <= exc.status_code < 500:
            return "failed_rejected"
        return "unknown"
    except (UnifiedCatalogTimeoutError, UnifiedCatalogRequestError):
        return "unknown"
    except UnifiedCatalogResponseError:
        return "unknown"
    except UnifiedCatalogClientError:
        return "unknown"
    except Exception:
        return "unknown"
    return "succeeded"


def _finalize_result_v3(
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
    operations: tuple[OperationResultV3, ...],
    failure: ExecutionFailure | None,
) -> ExecutionResultV3:
    result = build_execution_result_v3_from_parts(
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
    validate_result_document_v3_for_serialization(result.to_document())
    return result
