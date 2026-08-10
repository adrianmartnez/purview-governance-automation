"""Shared plan preconditions and semantic/canonical integrity validation."""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator

from purview_governance.config.diagnostics import ConfigValidationError
from purview_governance.config.models import GovernanceConfig
from purview_governance.config.normalize import normalize_endpoint
from purview_governance.config.validate import validate_document as validate_config_document
from purview_governance.data_source_endpoint import (
    DataSourceEndpointError,
    validate_data_source_endpoint,
)
from purview_governance.plan.errors import (
    PlanBuildError,
    PlanIntegrityError,
    PlanSchemaError,
)
from purview_governance.plan.identity import (
    CONFIGURATION_API_VERSION,
    PLAN_API_VERSION,
    compute_desired_state_identity,
    compute_material_configuration_identity,
    compute_plan_identity,
    compute_target_context_identity,
    is_sha256_identity,
)
from purview_governance.plan.schema import load_plan_v1_schema
from purview_governance.remote_state.canonical import (
    compute_material_state_identity,
    dumps_canonical,
)
from purview_governance.remote_state.models import (
    REMOTE_STATE_API_VERSION,
    RemoteState,
    UnknownLegacyMovingState,
)
from purview_governance.remote_state.schema import load_remote_state_v1_schema

CREATION_OWNERSHIP_REASON_CODES = frozenset(
    {
        "remote.creation_type_auto_native",
        "remote.creation_type_auto_managed",
    }
)

MOVING_STATE_REASON_CODES = frozenset(
    {
        "remote.collection_moving_state_uninterpreted",
        "remote.collection_moving",
        "remote.collection_move_failed",
    }
)

OWNERSHIP_SAFETY_REASON_CODES = CREATION_OWNERSHIP_REASON_CODES | MOVING_STATE_REASON_CODES

BLOCKING_REASON_CODES = frozenset(
    OWNERSHIP_SAFETY_REASON_CODES
    | {
        "properties.collection.referenceName.changed",
        "kind.changed",
        "remote_state.unsupported_kind",
    }
)

REASON_PATHS: dict[str, str] = {
    "desired.absent_remote": "/",
    "remote.absent_desired": "/",
    "properties.endpoint.changed": "/properties/endpoint",
    "properties.collection.referenceName.changed": "/properties/collection/referenceName",
    "remote.creation_type_auto_native": "/creationType",
    "remote.creation_type_auto_managed": "/creationType",
    "remote.collection_moving": "/properties/dataSourceCollectionMovingState",
    "remote.collection_move_failed": "/properties/dataSourceCollectionMovingState",
    "remote.collection_moving_state_uninterpreted": ("/properties/dataSourceCollectionMovingState"),
    "remote_state.unsupported_kind": "/kind",
    "kind.changed": "/kind",
}


def _integrity(code: str, message: str, *, path: str = "") -> PlanIntegrityError:
    return PlanIntegrityError(code, message, path=path)


def _raise_integrity(code: str, message: str, *, path: str = "") -> None:
    raise _integrity(code, message, path=path)


def validate_governance_config_for_planning(config: GovernanceConfig) -> str:
    """Revalidate a public GovernanceConfig; return normalized target endpoint."""
    document_failed = False
    document: dict[str, Any] | None = None
    try:
        document = config.to_document()
    except Exception:
        document_failed = True
    if document_failed or document is None:
        raise PlanBuildError(
            "plan.invalid_configuration_input",
            "governance configuration input could not be serialized",
        )

    config_invalid = False
    try:
        validate_config_document(document)
    except ConfigValidationError:
        config_invalid = True
    except Exception:
        config_invalid = True
    if config_invalid:
        raise PlanBuildError(
            "plan.invalid_configuration_input",
            "governance configuration input failed contract validation",
        )

    endpoint_failed = False
    normalized = ""
    try:
        normalized = normalize_endpoint(config.target.endpoint)
    except Exception:
        endpoint_failed = True
    if endpoint_failed:
        raise PlanBuildError(
            "plan.invalid_configuration_input",
            "governance configuration target endpoint is invalid",
            path="/target/endpoint",
        )

    for index, resource in enumerate(config.resources):
        if resource.kind != "AzureStorage":
            raise PlanBuildError(
                "plan.invalid_configuration_input",
                "data source kind must be AzureStorage",
                path=f"/resources/{index}/kind",
            )
        ref = resource.collection_reference_name
        if not isinstance(ref, str) or not ref.strip() or ref != ref.strip():
            raise PlanBuildError(
                "plan.invalid_configuration_input",
                "collection reference must be a non-empty strip-canonical string",
                path=f"/resources/{index}/properties/collection/referenceName",
            )

    return normalized


def validate_remote_state_for_planning(remote_state: RemoteState) -> None:
    """Validate RemoteState as canonical purview-remote-state/v1 planning input."""
    document_failed = False
    document: dict[str, Any] | None = None
    try:
        document = remote_state.to_document()
    except Exception:
        document_failed = True
    if document_failed or document is None:
        raise PlanBuildError(
            "plan.invalid_remote_state_input",
            "remote state input could not be serialized",
        )

    schema_failed = False
    try:
        schema = load_remote_state_v1_schema()
        Draft202012Validator(schema).validate(document)
    except Exception:
        schema_failed = True
    if schema_failed:
        raise PlanBuildError(
            "plan.invalid_remote_state_input",
            "remote state input failed schema validation",
        )

    ds_names = [item.name for item in remote_state.data_sources]
    ui_names = [item.name for item in remote_state.uninterpreted_data_sources]

    if ds_names != sorted(ds_names):
        raise PlanBuildError(
            "plan.invalid_remote_state_input",
            "remote dataSources must be sorted by name",
            path="/dataSources",
        )
    if ui_names != sorted(ui_names):
        raise PlanBuildError(
            "plan.invalid_remote_state_input",
            "remote uninterpretedDataSources must be sorted by name",
            path="/uninterpretedDataSources",
        )
    if len(ds_names) != len(set(ds_names)):
        raise PlanBuildError(
            "plan.invalid_remote_state_input",
            "remote dataSources names must be unique",
            path="/dataSources",
        )
    if len(ui_names) != len(set(ui_names)):
        raise PlanBuildError(
            "plan.invalid_remote_state_input",
            "remote uninterpretedDataSources names must be unique",
            path="/uninterpretedDataSources",
        )
    overlap = set(ds_names) & set(ui_names)
    if overlap:
        raise PlanBuildError(
            "plan.invalid_remote_state_input",
            "remote supported and uninterpreted names must not overlap",
            path="/dataSources",
        )

    for index, item in enumerate(remote_state.data_sources):
        if item.kind != "AzureStorage":
            raise PlanBuildError(
                "plan.invalid_remote_state_input",
                "supported remote data source kind must be AzureStorage",
                path=f"/dataSources/{index}/kind",
            )
        endpoint_ok = True
        validated = ""
        try:
            validated = validate_data_source_endpoint(item.endpoint)
        except DataSourceEndpointError:
            endpoint_ok = False
        if not endpoint_ok or validated != item.endpoint:
            raise PlanBuildError(
                "plan.invalid_remote_state_input",
                "supported remote endpoint must be safe and canonical",
                path=f"/dataSources/{index}/properties/endpoint",
            )
        ref = item.collection_reference_name
        if not isinstance(ref, str) or not ref.strip() or ref != ref.strip():
            raise PlanBuildError(
                "plan.invalid_remote_state_input",
                "supported remote collection reference must be strip-canonical",
                path=f"/dataSources/{index}/properties/collection/referenceName",
            )
        if item.creation_type not in {"Manual", "AutoNative", "AutoManaged"}:
            raise PlanBuildError(
                "plan.invalid_remote_state_input",
                "supported remote creationType is invalid",
                path=f"/dataSources/{index}/creationType",
            )
        moving = item.collection_moving_state
        if isinstance(moving, UnknownLegacyMovingState):
            if moving.raw != "0":
                raise PlanBuildError(
                    "plan.invalid_remote_state_input",
                    "unsupported legacy moving state",
                    path=f"/dataSources/{index}/properties/dataSourceCollectionMovingState",
                )
        elif moving not in {"Active", "Moving", "Failed"}:
            raise PlanBuildError(
                "plan.invalid_remote_state_input",
                "supported remote moving state is invalid",
                path=f"/dataSources/{index}/properties/dataSourceCollectionMovingState",
            )

    for index, item in enumerate(remote_state.uninterpreted_data_sources):
        if item.reason_code != "remote_state.unsupported_kind":
            raise PlanBuildError(
                "plan.invalid_remote_state_input",
                "uninterpreted reasonCode must be remote_state.unsupported_kind",
                path=f"/uninterpretedDataSources/{index}/reasonCode",
            )
        if item.kind == "AzureStorage":
            raise PlanBuildError(
                "plan.invalid_remote_state_input",
                "uninterpreted unsupported_kind must not use AzureStorage kind",
                path=f"/uninterpretedDataSources/{index}/kind",
            )

    identity_doc_failed = False
    expected = ""
    try:
        expected = compute_material_state_identity(remote_state.identity_document())
    except Exception:
        identity_doc_failed = True
    if identity_doc_failed:
        raise PlanBuildError(
            "plan.invalid_remote_state_input",
            "remote state identity document is invalid",
        )
    if expected != remote_state.material_state_identity:
        raise PlanBuildError(
            "plan.inconsistent_remote_identity",
            "remote materialStateIdentity does not match recomputed identity",
            path="/materialStateIdentity",
        )

    # Ensure identity document carries the expected remote-state contract version.
    identity_document = remote_state.identity_document()
    if identity_document.get("apiVersion") != REMOTE_STATE_API_VERSION:
        raise PlanBuildError(
            "plan.invalid_remote_state_input",
            "remote state identity document apiVersion is unsupported",
            path="/apiVersion",
        )


def _validate_endpoint_value(value: object, *, path: str) -> str:
    endpoint_failed = False
    validated = ""
    try:
        validated = validate_data_source_endpoint(value)
    except DataSourceEndpointError:
        endpoint_failed = True
    if endpoint_failed:
        _raise_integrity(
            "plan.noncanonical_input",
            "endpoint value is invalid or unsafe",
            path=path,
        )
    if not isinstance(value, str) or validated != value:
        _raise_integrity(
            "plan.noncanonical_input",
            "endpoint value must be strip-canonical",
            path=path,
        )
    return validated


def _validate_reason_shape(reason: dict[str, Any], *, path: str) -> None:
    code = reason.get("code")
    reason_path = reason.get("path")
    if not isinstance(code, str) or code not in REASON_PATHS:
        _raise_integrity("plan.invalid_reason", "unknown or unsupported reason code", path=path)
    if reason_path != REASON_PATHS[code]:
        _raise_integrity("plan.invalid_reason", "reason path does not match code", path=path)

    has_before = "before" in reason
    has_after = "after" in reason
    before = reason.get("before")
    after = reason.get("after")

    if code in {"desired.absent_remote", "remote.absent_desired"}:
        if has_before or has_after:
            _raise_integrity("plan.invalid_reason", "reason forbids before/after", path=path)
        return

    if code == "properties.endpoint.changed":
        if not has_before or not has_after:
            _raise_integrity(
                "plan.invalid_reason", "endpoint reason requires before and after", path=path
            )
        before_v = _validate_endpoint_value(before, path=f"{path}/before")
        after_v = _validate_endpoint_value(after, path=f"{path}/after")
        if before_v == after_v:
            _raise_integrity(
                "plan.invalid_reason", "endpoint before and after must differ", path=path
            )
        return

    if code == "properties.collection.referenceName.changed":
        if not has_before or not has_after:
            _raise_integrity(
                "plan.invalid_reason",
                "collection reason requires before and after",
                path=path,
            )
        for label, value in (("before", before), ("after", after)):
            if not isinstance(value, str) or not value.strip() or value != value.strip():
                _raise_integrity(
                    "plan.invalid_reason",
                    "collection reference must be strip-canonical",
                    path=f"{path}/{label}",
                )
        if before == after:
            _raise_integrity(
                "plan.invalid_reason",
                "collection before and after must differ",
                path=path,
            )
        return

    exact_before: dict[str, str] = {
        "remote.creation_type_auto_native": "AutoNative",
        "remote.creation_type_auto_managed": "AutoManaged",
        "remote.collection_moving": "Moving",
        "remote.collection_move_failed": "Failed",
        "remote.collection_moving_state_uninterpreted": "0",
    }
    if code in exact_before:
        if not has_before or has_after:
            _raise_integrity(
                "plan.invalid_reason",
                "reason requires exact before and forbids after",
                path=path,
            )
        if before != exact_before[code]:
            _raise_integrity("plan.invalid_reason", "reason before value is invalid", path=path)
        return

    if code == "remote_state.unsupported_kind":
        if not has_before or has_after:
            _raise_integrity(
                "plan.invalid_reason",
                "unsupported_kind requires before and forbids after",
                path=path,
            )
        if not isinstance(before, str) or not before:
            _raise_integrity(
                "plan.invalid_reason", "unsupported_kind before must be non-empty", path=path
            )
        if before == "AzureStorage":
            _raise_integrity(
                "plan.invalid_reason",
                "unsupported_kind before must not be AzureStorage",
                path=path,
            )
        return

    if code == "kind.changed":
        if not has_before or not has_after:
            _raise_integrity(
                "plan.invalid_reason", "kind.changed requires before and after", path=path
            )
        if not isinstance(before, str) or not before:
            _raise_integrity(
                "plan.invalid_reason", "kind.changed before must be non-empty", path=path
            )
        if after != "AzureStorage":
            _raise_integrity(
                "plan.invalid_reason", "kind.changed after must be AzureStorage", path=path
            )
        if before == after:
            _raise_integrity("plan.invalid_reason", "kind before and after must differ", path=path)
        return

    _raise_integrity("plan.invalid_reason", "unsupported reason code", path=path)


def _reason_codes(reasons: list[dict[str, Any]]) -> list[str]:
    return [str(item["code"]) for item in reasons]


def _assert_exclusive_ownership_groups(codes: list[str], *, path: str) -> None:
    creation_count = sum(1 for code in codes if code in CREATION_OWNERSHIP_REASON_CODES)
    moving_count = sum(1 for code in codes if code in MOVING_STATE_REASON_CODES)
    if creation_count > 1:
        _raise_integrity(
            "plan.invalid_reason_outcome",
            "at most one creation ownership reason is allowed",
            path=path,
        )
    if moving_count > 1:
        _raise_integrity(
            "plan.invalid_reason_outcome",
            "at most one moving-state reason is allowed",
            path=path,
        )


def _bind_reason_after_to_desired(
    reasons: list[dict[str, Any]],
    desired: dict[str, Any] | None,
    *,
    path: str,
) -> None:
    """Require material reason.after values to match the desired snapshot authority."""
    if desired is None:
        return
    desired_endpoint = desired["properties"]["endpoint"]
    desired_collection = desired["properties"]["collection"]["referenceName"]
    desired_kind = desired["kind"]
    for index, reason in enumerate(reasons):
        code = reason["code"]
        reason_path = f"{path}/reasons/{index}"
        if code == "properties.endpoint.changed":
            if reason.get("after") != desired_endpoint:
                _raise_integrity(
                    "plan.invalid_reason_outcome",
                    "endpoint reason after must equal desired endpoint",
                    path=reason_path,
                )
        elif code == "properties.collection.referenceName.changed":
            if reason.get("after") != desired_collection:
                _raise_integrity(
                    "plan.invalid_reason_outcome",
                    "collection reason after must equal desired collection reference",
                    path=reason_path,
                )
        elif code == "kind.changed" and reason.get("after") != desired_kind:
            _raise_integrity(
                "plan.invalid_reason_outcome",
                "kind.changed after must equal desired kind",
                path=reason_path,
            )


def _validate_unsupported_reason_pair(
    reasons: list[dict[str, Any]],
    *,
    has_desired: bool,
    desired: dict[str, Any] | None,
    path: str,
) -> None:
    by_code = {reason["code"]: reason for reason in reasons}
    unsupported = by_code["remote_state.unsupported_kind"]
    if has_desired:
        kind_changed = by_code["kind.changed"]
        if unsupported.get("before") != kind_changed.get("before"):
            _raise_integrity(
                "plan.invalid_reason_outcome",
                "unsupported_kind and kind.changed before values must match",
                path=path,
            )
        if desired is None or kind_changed.get("after") != desired["kind"]:
            _raise_integrity(
                "plan.invalid_reason_outcome",
                "kind.changed after must equal desired kind",
                path=path,
            )


def _validate_outcome_reasons(
    *,
    outcome: str,
    reasons: list[dict[str, Any]],
    has_desired: bool,
    desired: dict[str, Any] | None,
    path: str,
) -> None:
    codes = _reason_codes(reasons)
    _bind_reason_after_to_desired(reasons, desired, path=path)

    if outcome == "create":
        if not has_desired:
            _raise_integrity(
                "plan.invalid_membership", "create requires desired resource", path=path
            )
        if codes != ["desired.absent_remote"]:
            _raise_integrity(
                "plan.invalid_reason_outcome",
                "create reasons must be exactly desired.absent_remote",
                path=path,
            )
        return

    if outcome == "replace":
        if not has_desired:
            _raise_integrity(
                "plan.invalid_membership", "replace requires desired resource", path=path
            )
        if codes != ["properties.endpoint.changed"]:
            _raise_integrity(
                "plan.invalid_reason_outcome",
                "replace reasons must be exactly properties.endpoint.changed",
                path=path,
            )
        return

    if outcome == "no-op":
        if not has_desired:
            _raise_integrity(
                "plan.invalid_membership", "no-op requires desired resource", path=path
            )
        if reasons:
            _raise_integrity(
                "plan.invalid_reason_outcome",
                "no-op reasons must be empty",
                path=path,
            )
        return

    if outcome == "remote-only":
        if has_desired:
            _raise_integrity(
                "plan.invalid_membership",
                "remote-only must not have a desired resource",
                path=path,
            )
        if "remote.absent_desired" not in codes:
            _raise_integrity(
                "plan.invalid_reason_outcome",
                "remote-only must include remote.absent_desired",
                path=path,
            )
        allowed = OWNERSHIP_SAFETY_REASON_CODES | {"remote.absent_desired"}
        if any(code not in allowed for code in codes):
            _raise_integrity(
                "plan.invalid_reason_outcome",
                "remote-only contains disallowed reason codes",
                path=path,
            )
        _assert_exclusive_ownership_groups(codes, path=path)
        return

    if outcome == "blocked":
        if not reasons:
            _raise_integrity(
                "plan.invalid_reason_outcome",
                "blocked item must include at least one reason",
                path=path,
            )
        if not any(code in BLOCKING_REASON_CODES for code in codes):
            _raise_integrity(
                "plan.invalid_reason_outcome",
                "blocked item must include a blocking reason",
                path=path,
            )

        has_unsupported = "remote_state.unsupported_kind" in codes
        has_kind_changed = "kind.changed" in codes
        has_absent_desired = "remote.absent_desired" in codes

        if has_unsupported:
            if has_desired:
                if not has_kind_changed or has_absent_desired:
                    _raise_integrity(
                        "plan.invalid_reason_outcome",
                        "unsupported blocked with desired must include kind.changed only",
                        path=path,
                    )
                expected = {"remote_state.unsupported_kind", "kind.changed"}
                if set(codes) != expected:
                    _raise_integrity(
                        "plan.invalid_reason_outcome",
                        "unsupported blocked with desired has invalid reasons",
                        path=path,
                    )
                _validate_unsupported_reason_pair(
                    reasons,
                    has_desired=True,
                    desired=desired,
                    path=path,
                )
            else:
                if has_kind_changed or not has_absent_desired:
                    _raise_integrity(
                        "plan.invalid_reason_outcome",
                        "unsupported blocked without desired must include remote.absent_desired",
                        path=path,
                    )
                expected = {"remote_state.unsupported_kind", "remote.absent_desired"}
                if set(codes) != expected:
                    _raise_integrity(
                        "plan.invalid_reason_outcome",
                        "unsupported blocked without desired has invalid reasons",
                        path=path,
                    )
            return

        # Supported remote + desired blocked (kind.changed is not a v1 diff outcome here).
        if has_absent_desired or "desired.absent_remote" in codes:
            _raise_integrity(
                "plan.invalid_reason_outcome",
                "supported blocked must not include absence reasons",
                path=path,
            )
        if not has_desired:
            _raise_integrity(
                "plan.invalid_membership",
                "supported blocked requires desired resource",
                path=path,
            )
        allowed = OWNERSHIP_SAFETY_REASON_CODES | {
            "properties.collection.referenceName.changed",
            "properties.endpoint.changed",
        }
        if any(code not in allowed for code in codes):
            _raise_integrity(
                "plan.invalid_reason_outcome",
                "supported blocked contains disallowed reason codes",
                path=path,
            )
        _assert_exclusive_ownership_groups(codes, path=path)
        core_blocking = OWNERSHIP_SAFETY_REASON_CODES | {
            "properties.collection.referenceName.changed",
        }
        if not any(code in core_blocking for code in codes):
            _raise_integrity(
                "plan.invalid_reason_outcome",
                "supported blocked missing core blocking reason",
                path=path,
            )
        return

    _raise_integrity("plan.invalid_reason_outcome", "unsupported outcome", path=path)


def validate_plan_document_semantics(document: dict[str, Any]) -> None:
    """Validate semantic/canonical integrity of a plain plan document (no recursion)."""
    if document.get("apiVersion") != PLAN_API_VERSION:
        _raise_integrity(
            "plan.unsupported_version", "unsupported plan apiVersion", path="/apiVersion"
        )
    if document.get("configurationApiVersion") != CONFIGURATION_API_VERSION:
        _raise_integrity(
            "plan.invalid_schema",
            "configurationApiVersion mismatch",
            path="/configurationApiVersion",
        )

    target = document["targetContext"]
    endpoint = target["endpoint"]
    target_failed = False
    normalized_target = ""
    try:
        normalized_target = normalize_endpoint(endpoint)
    except Exception:
        target_failed = True
    if target_failed or normalized_target != endpoint:
        _raise_integrity(
            "plan.noncanonical_input",
            "target endpoint must equal normalize_endpoint output",
            path="/targetContext/endpoint",
        )
    expected_target_identity = compute_target_context_identity(endpoint)
    if target.get("identity") != expected_target_identity:
        _raise_integrity(
            "plan.identity_mismatch",
            "targetContext.identity mismatch",
            path="/targetContext/identity",
        )

    desired_doc = document["desiredState"]
    data_sources = desired_doc.get("dataSources", [])
    desired_names = [item["name"] for item in data_sources]
    if desired_names != sorted(desired_names):
        _raise_integrity(
            "plan.noncanonical_input",
            "desired dataSources must be sorted by name",
            path="/desiredState/dataSources",
        )
    if len(desired_names) != len(set(desired_names)):
        _raise_integrity(
            "plan.invalid_membership",
            "desired dataSources names must be unique",
            path="/desiredState/dataSources",
        )
    desired_by_name = {item["name"]: item for item in data_sources}

    for index, item in enumerate(data_sources):
        _validate_endpoint_value(
            item["properties"]["endpoint"],
            path=f"/desiredState/dataSources/{index}/properties/endpoint",
        )
        ref = item["properties"]["collection"]["referenceName"]
        if not isinstance(ref, str) or not ref.strip() or ref != ref.strip():
            _raise_integrity(
                "plan.noncanonical_input",
                "desired collection reference must be strip-canonical",
                path=f"/desiredState/dataSources/{index}/properties/collection/referenceName",
            )

    expected_desired_identity = compute_desired_state_identity(desired_doc)
    identities = document["identities"]
    if identities.get("desiredState") != expected_desired_identity:
        _raise_integrity(
            "plan.identity_mismatch",
            "identities.desiredState mismatch",
            path="/identities/desiredState",
        )
    expected_material = compute_material_configuration_identity(
        target_context_identity=expected_target_identity,
        desired_state_identity=expected_desired_identity,
    )
    if identities.get("materialConfiguration") != expected_material:
        _raise_integrity(
            "plan.identity_mismatch",
            "identities.materialConfiguration mismatch",
            path="/identities/materialConfiguration",
        )
    if not is_sha256_identity(identities.get("remoteState")):
        _raise_integrity(
            "plan.identity_mismatch",
            "identities.remoteState hash format is invalid",
            path="/identities/remoteState",
        )

    change_items = document["changeSet"]["items"]
    change_names = [item["name"] for item in change_items]
    if change_names != sorted(change_names):
        _raise_integrity(
            "plan.noncanonical_input",
            "changeSet items must be sorted by name",
            path="/changeSet/items",
        )
    if len(change_names) != len(set(change_names)):
        _raise_integrity(
            "plan.invalid_membership",
            "changeSet names must be unique",
            path="/changeSet/items",
        )

    desired_name_set = set(desired_names)
    for name in desired_names:
        if name not in change_names:
            _raise_integrity(
                "plan.invalid_membership",
                "desired resource missing from changeSet",
                path="/changeSet/items",
            )

    counts = {
        "create": 0,
        "replace": 0,
        "no-op": 0,
        "remote-only": 0,
        "blocked": 0,
    }
    for index, item in enumerate(change_items):
        item_path = f"/changeSet/items/{index}"
        outcome = item["outcome"]
        if outcome not in counts:
            _raise_integrity("plan.invalid_reason_outcome", "unknown outcome", path=item_path)
        counts[outcome] += 1
        reasons = item["reasons"]
        reason_keys: set[tuple[Any, ...]] = set()
        previous_sort: tuple[str, str] | None = None
        for r_index, reason in enumerate(reasons):
            r_path = f"{item_path}/reasons/{r_index}"
            _validate_reason_shape(reason, path=r_path)
            key = (
                reason.get("path"),
                reason.get("code"),
                reason.get("before"),
                reason.get("after"),
            )
            if key in reason_keys:
                _raise_integrity("plan.invalid_reason", "duplicate reason", path=r_path)
            reason_keys.add(key)
            sort_key = (str(reason.get("path")), str(reason.get("code")))
            if previous_sort is not None and sort_key < previous_sort:
                _raise_integrity(
                    "plan.noncanonical_input",
                    "reasons must be ordered by path then code",
                    path=r_path,
                )
            previous_sort = sort_key

        _validate_outcome_reasons(
            outcome=outcome,
            reasons=reasons,
            has_desired=item["name"] in desired_name_set,
            desired=desired_by_name.get(item["name"]),
            path=item_path,
        )

    operations = document["operations"]
    expected_ops: list[tuple[str, str]] = []
    for item in change_items:
        if item["outcome"] in {"create", "replace"}:
            expected_ops.append((item["outcome"], item["name"]))
    expected_ops.sort(key=lambda pair: ("dataSource", pair[1]))

    if len(operations) != len(expected_ops):
        _raise_integrity(
            "plan.invalid_operation_mapping",
            "operations must match create/replace changeSet items",
            path="/operations",
        )

    previous_name: str | None = None
    for index, operation in enumerate(operations):
        op_path = f"/operations/{index}"
        if operation.get("sequence") != index + 1:
            _raise_integrity(
                "plan.invalid_operation_mapping",
                "operation sequence must be contiguous from 1",
                path=op_path,
            )
        if operation.get("type") != "dataSource":
            _raise_integrity(
                "plan.invalid_operation_mapping",
                "operation type must be dataSource",
                path=op_path,
            )
        action = operation.get("action")
        name = operation.get("name")
        if action not in {"create", "replace"}:
            _raise_integrity(
                "plan.invalid_operation_mapping",
                "operation action must be create or replace",
                path=op_path,
            )
        if name not in desired_name_set:
            _raise_integrity(
                "plan.invalid_operation_mapping",
                "operation references unknown desired resource",
                path=op_path,
            )
        if previous_name is not None and str(name) < previous_name:
            _raise_integrity(
                "plan.noncanonical_input",
                "operations must be ordered by type then name",
                path=op_path,
            )
        previous_name = str(name)
        expected_action, expected_name = expected_ops[index]
        if name != expected_name or action != expected_action:
            _raise_integrity(
                "plan.invalid_operation_mapping",
                "operation does not match changeSet create/replace mapping",
                path=op_path,
            )

    summary = document["summary"]
    expected_summary = {
        "total": len(change_items),
        "create": counts["create"],
        "replace": counts["replace"],
        "noOp": counts["no-op"],
        "remoteOnly": counts["remote-only"],
        "blocked": counts["blocked"],
        "operations": len(operations),
    }
    if summary != expected_summary:
        _raise_integrity(
            "plan.invalid_summary", "summary counts do not match changeSet", path="/summary"
        )

    expected_eligibility = "blocked" if counts["blocked"] > 0 else "ready"
    if document.get("executionEligibility") != expected_eligibility:
        _raise_integrity(
            "plan.invalid_eligibility",
            "executionEligibility does not match blocked count",
            path="/executionEligibility",
        )

    without_identity = {key: value for key, value in document.items() if key != "planIdentity"}
    expected_plan_identity = compute_plan_identity(without_identity)
    if document.get("planIdentity") != expected_plan_identity:
        _raise_integrity(
            "plan.identity_mismatch",
            "planIdentity mismatch",
            path="/planIdentity",
        )


def validate_plan_document_schema(document: dict[str, Any]) -> None:
    schema_failed = False
    try:
        schema = load_plan_v1_schema()
        Draft202012Validator(schema).validate(document)
    except Exception:
        schema_failed = True
    if schema_failed:
        raise PlanSchemaError("plan.invalid_schema", "plan document failed schema validation")


def validate_plan_document_for_serialization(document: dict[str, Any]) -> None:
    """Schema + semantic validation for the official serializer boundary."""
    validate_plan_document_schema(document)
    validate_plan_document_semantics(document)


def dumps_plan_canonical(document: dict[str, Any]) -> str:
    """Validate then emit canonical plan JSON."""
    validate_plan_document_for_serialization(document)
    return dumps_canonical(document)
