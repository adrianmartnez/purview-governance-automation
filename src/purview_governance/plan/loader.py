"""Strict JSON loader for purview-governance-plan/v1 and /v2."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from purview_governance.plan.errors import (
    PlanIntegrityError,
    PlanLoadError,
    PlanSchemaError,
    PlanVersionError,
)
from purview_governance.plan.identity import (
    PLAN_API_VERSION,
    PLAN_API_VERSION_V2,
    PLAN_API_VERSION_V3,
)
from purview_governance.plan.models import (
    GovernancePlan,
    PlanIdentities,
    PlanTargetContext,
    change_set_from_document,
    desired_state_from_document,
    operations_from_document,
    summary_from_document,
)
from purview_governance.plan.models_v3 import (
    GovernancePlanV3,
    PlanTargetContextV3,
    change_set_v3_from_document,
    desired_state_v3_from_document,
    operations_v3_from_document,
)
from purview_governance.plan.models_v3 import (
    summary_from_document as summary_v3_from_document,
)
from purview_governance.plan.validation import (
    validate_plan_document_schema,
    validate_plan_document_semantics,
)
from purview_governance.plan.validation_v3 import (
    validate_plan_document_schema_v3,
    validate_plan_document_semantics_v3,
)


class DuplicateKeyError(ValueError):
    """Internal signal that a mapping contains a duplicated key."""

    def __init__(self, key: object) -> None:
        self.key = key
        super().__init__(f"duplicate key {key!r}")


def _object_pairs_hook(pairs: list[tuple[Any, Any]]) -> dict[Any, Any]:
    result: dict[Any, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(key)
        result[key] = value
    return result


def _parse_plan_json(text: str) -> dict[str, Any]:
    duplicate = False
    syntax_failed = False
    document: Any = None
    try:
        document = json.loads(text, object_pairs_hook=_object_pairs_hook)
    except DuplicateKeyError:
        duplicate = True
    except json.JSONDecodeError:
        syntax_failed = True
    if duplicate:
        raise PlanLoadError("plan.duplicate_key", "duplicate object keys are not allowed")
    if syntax_failed:
        raise PlanLoadError("plan.invalid_syntax", "plan document is not valid JSON")
    if not isinstance(document, dict):
        raise PlanLoadError("plan.invalid_syntax", "plan document must be a JSON object")
    return document


def _governance_plan_from_validated_document(document: dict[str, Any]) -> GovernancePlan:
    target = document["targetContext"]
    identities = document["identities"]
    return GovernancePlan(
        api_version=document["apiVersion"],
        configuration_api_version=document["configurationApiVersion"],
        target_context=PlanTargetContext(
            endpoint=target["endpoint"],
            identity=target["identity"],
        ),
        identities=PlanIdentities(
            material_configuration=identities["materialConfiguration"],
            desired_state=identities["desiredState"],
            remote_state=identities["remoteState"],
        ),
        desired_state=desired_state_from_document(document["desiredState"]),
        change_set=change_set_from_document(document["changeSet"]),
        execution_eligibility=document["executionEligibility"],
        operations=operations_from_document(document["operations"]),
        summary=summary_from_document(document["summary"]),
        plan_identity=document["planIdentity"],
    )


def _materialize_plan_v1_or_v2(document: dict[str, Any]) -> GovernancePlan:
    """Schema + semantic validation + model for an already-parsed v1/v2 document."""
    api_version = document.get("apiVersion")
    if api_version not in {PLAN_API_VERSION, PLAN_API_VERSION_V2}:
        raise PlanVersionError(
            "plan.unsupported_version",
            "unsupported or missing plan apiVersion",
            path="/apiVersion",
        )

    # Pre-#27 plan/v2 development shape (desiredState without classificationRules)
    # is superseded; refuse load before generic schema failure (no upconvert).
    if api_version == PLAN_API_VERSION_V2:
        desired_state = document.get("desiredState")
        if isinstance(desired_state, dict) and "classificationRules" not in desired_state:
            raise PlanSchemaError(
                "plan.development_shape_superseded",
                "pre-#27 plan/v2 development shape is superseded; "
                "desiredState.classificationRules is required (no upconvert)",
                path="/desiredState",
            )

    schema_failed = False
    try:
        validate_plan_document_schema(document)
    except PlanSchemaError:
        schema_failed = True
    except Exception:
        schema_failed = True
    if schema_failed:
        raise PlanSchemaError("plan.invalid_schema", "plan document failed schema validation")

    integrity_failed = False
    integrity_error: PlanIntegrityError | None = None
    try:
        validate_plan_document_semantics(document)
    except PlanIntegrityError as exc:
        integrity_failed = True
        integrity_error = PlanIntegrityError(exc.code, exc.message, path=exc.path)
    except Exception:
        integrity_failed = True
        integrity_error = PlanIntegrityError(
            "plan.identity_mismatch",
            "plan document failed semantic integrity validation",
        )
    if integrity_failed:
        assert integrity_error is not None
        raise integrity_error

    model_failed = False
    plan: GovernancePlan | None = None
    try:
        plan = _governance_plan_from_validated_document(document)
    except Exception:
        model_failed = True
    if model_failed or plan is None:
        raise PlanIntegrityError(
            "plan.invalid_schema",
            "plan document could not be materialized",
        )
    return plan


def load_plan_text(text: str) -> GovernancePlan:
    """Load and strictly validate a purview-governance-plan/v1 or /v2 JSON artifact."""
    document = _parse_plan_json(text)
    return _materialize_plan_v1_or_v2(document)


def load_plan_file(path: str | Path) -> GovernancePlan:
    """Load a plan artifact from a UTF-8 JSON file."""
    file_path = Path(path)
    read_failed = False
    text = ""
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError:
        read_failed = True
    if read_failed:
        raise PlanLoadError("plan.invalid_syntax", "plan file could not be read")
    return load_plan_text(text)


def _governance_plan_v3_from_validated_document(document: dict[str, Any]) -> GovernancePlanV3:
    target = document["targetContext"]
    identities = document["identities"]

    return GovernancePlanV3(
        api_version=document["apiVersion"],
        configuration_api_version=document["configurationApiVersion"],
        target_context=PlanTargetContextV3(
            surface=target["surface"],
            tenant_id=target["tenantId"],
            endpoint=target["endpoint"],
            identity=target["identity"],
        ),
        identities=PlanIdentities(
            material_configuration=identities["materialConfiguration"],
            desired_state=identities["desiredState"],
            remote_state=identities["remoteState"],
        ),
        desired_state=desired_state_v3_from_document(document["desiredState"]),
        change_set=change_set_v3_from_document(document["changeSet"]),
        execution_eligibility=document["executionEligibility"],
        operations=operations_v3_from_document(document["operations"]),
        summary=summary_v3_from_document(document["summary"]),
        plan_identity=document["planIdentity"],
    )


def _materialize_plan_v3(document: dict[str, Any]) -> GovernancePlanV3:
    """Schema + semantic validation + model for an already-parsed v3 document."""
    api_version = document.get("apiVersion")
    if api_version != PLAN_API_VERSION_V3:
        raise PlanVersionError(
            "plan.unsupported_version",
            "unsupported or missing plan apiVersion for v3 loader",
            path="/apiVersion",
        )

    schema_failed = False
    try:
        validate_plan_document_schema_v3(document)
    except PlanSchemaError:
        schema_failed = True
    except Exception:
        schema_failed = True
    if schema_failed:
        raise PlanSchemaError("plan.invalid_schema", "plan document failed schema validation")

    integrity_failed = False
    integrity_error: PlanIntegrityError | None = None
    try:
        validate_plan_document_semantics_v3(document)
    except PlanIntegrityError as exc:
        integrity_failed = True
        integrity_error = PlanIntegrityError(exc.code, exc.message, path=exc.path)
    except Exception:
        integrity_failed = True
        integrity_error = PlanIntegrityError(
            "plan.identity_mismatch",
            "plan document failed semantic integrity validation",
        )
    if integrity_failed:
        assert integrity_error is not None
        raise integrity_error

    model_failed = False
    plan: GovernancePlanV3 | None = None
    try:
        plan = _governance_plan_v3_from_validated_document(document)
    except Exception:
        model_failed = True
    if model_failed or plan is None:
        raise PlanIntegrityError(
            "plan.invalid_schema",
            "plan document could not be materialized",
        )
    return plan


def load_plan_v3_text(text: str) -> GovernancePlanV3:
    """Load and strictly validate a purview-governance-plan/v3 JSON artifact."""
    document = _parse_plan_json(text)
    return _materialize_plan_v3(document)


def load_plan_v3_file(path: str | Path) -> GovernancePlanV3:
    """Load a plan/v3 artifact from a UTF-8 JSON file."""
    file_path = Path(path)
    read_failed = False
    text = ""
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError:
        read_failed = True
    if read_failed:
        raise PlanLoadError("plan.invalid_syntax", "plan file could not be read")
    return load_plan_v3_text(text)


def _load_plan_any_version_text(text: str) -> GovernancePlan | GovernancePlanV3:
    """Strict once-parse version dispatch for plan/v1, /v2, or /v3."""
    document = _parse_plan_json(text)
    api_version = document.get("apiVersion")
    if api_version == PLAN_API_VERSION_V3:
        return _materialize_plan_v3(document)
    if api_version in {PLAN_API_VERSION, PLAN_API_VERSION_V2}:
        return _materialize_plan_v1_or_v2(document)
    raise PlanVersionError(
        "plan.unsupported_version",
        "unsupported or missing plan apiVersion",
        path="/apiVersion",
    )


def _load_plan_any_version_file(path: str | Path) -> GovernancePlan | GovernancePlanV3:
    """Load a plan/v1, /v2, or /v3 artifact from a UTF-8 JSON file (once-parse)."""
    file_path = Path(path)
    read_failed = False
    text = ""
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError:
        read_failed = True
    if read_failed:
        raise PlanLoadError("plan.invalid_syntax", "plan file could not be read")
    return _load_plan_any_version_text(text)
