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
from purview_governance.plan.identity import PLAN_API_VERSION, PLAN_API_VERSION_V2
from purview_governance.plan.models import (
    GovernancePlan,
    PlanIdentities,
    PlanTargetContext,
    change_set_from_document,
    desired_state_from_document,
    operations_from_document,
    summary_from_document,
)
from purview_governance.plan.validation import (
    validate_plan_document_schema,
    validate_plan_document_semantics,
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


def load_plan_text(text: str) -> GovernancePlan:
    """Load and strictly validate a purview-governance-plan/v1 or /v2 JSON artifact."""
    document = _parse_plan_json(text)

    api_version = document.get("apiVersion")
    if api_version not in {PLAN_API_VERSION, PLAN_API_VERSION_V2}:
        raise PlanVersionError(
            "plan.unsupported_version",
            "unsupported or missing plan apiVersion",
            path="/apiVersion",
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
