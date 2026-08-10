"""Strict JSON loader for purview-execution-result/v1."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from purview_governance.apply.errors import (
    ExecutionResultIntegrityError,
    ExecutionResultLoadError,
    ExecutionResultSchemaError,
    ExecutionResultVersionError,
)
from purview_governance.apply.identity import RESULT_API_VERSION
from purview_governance.apply.models import (
    ExecutionFailure,
    ExecutionMode,
    ExecutionResult,
    operations_from_document,
)
from purview_governance.apply.validation import (
    validate_result_document_schema,
    validate_result_document_semantics,
)


class DuplicateKeyError(ValueError):
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


def _parse_result_json(text: str) -> dict[str, Any]:
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
        raise ExecutionResultLoadError(
            "apply.duplicate_key",
            "duplicate object keys are not allowed",
        )
    if syntax_failed:
        raise ExecutionResultLoadError(
            "apply.invalid_syntax",
            "execution result is not valid JSON",
        )
    if not isinstance(document, dict):
        raise ExecutionResultLoadError(
            "apply.invalid_syntax",
            "execution result must be a JSON object",
        )
    return document


def _result_from_validated_document(document: dict[str, Any]) -> ExecutionResult:
    failure_raw = document["failure"]
    failure = None if failure_raw is None else ExecutionFailure(code=failure_raw["code"])
    return ExecutionResult(
        api_version=document["apiVersion"],
        plan_identity=document["planIdentity"],
        planned_target_context_identity=document["plannedTargetContextIdentity"],
        execution_target_context_identity=document["executionTargetContextIdentity"],
        planned_remote_state_identity=document["plannedRemoteStateIdentity"],
        observed_remote_state_identity=document["observedRemoteStateIdentity"],
        mode=ExecutionMode(document["mode"]),
        status=document["status"],
        writes_performed=document["writesPerformed"],
        writes_attempted=document["writesAttempted"],
        writes_unknown=document["writesUnknown"],
        operations=operations_from_document(document["operations"]),
        failure=failure,
        result_identity=document["resultIdentity"],
    )


def load_execution_result_text(text: str) -> ExecutionResult:
    """Load and strictly validate a purview-execution-result/v1 JSON artifact."""
    document = _parse_result_json(text)

    api_version = document.get("apiVersion")
    if api_version != RESULT_API_VERSION:
        raise ExecutionResultVersionError(
            "apply.unsupported_version",
            "unsupported or missing execution-result apiVersion",
            path="/apiVersion",
        )

    schema_failed = False
    try:
        validate_result_document_schema(document)
    except ExecutionResultSchemaError:
        schema_failed = True
    except Exception:
        schema_failed = True
    if schema_failed:
        raise ExecutionResultSchemaError(
            "apply.invalid_result_schema",
            "execution result failed schema validation",
        )

    integrity_failed = False
    integrity_error: ExecutionResultIntegrityError | None = None
    try:
        validate_result_document_semantics(document)
    except ExecutionResultIntegrityError as exc:
        integrity_failed = True
        integrity_error = ExecutionResultIntegrityError(exc.code, exc.message, path=exc.path)
    except Exception:
        integrity_failed = True
        integrity_error = ExecutionResultIntegrityError(
            "apply.result_identity_mismatch",
            "execution result failed semantic integrity validation",
        )
    if integrity_failed:
        assert integrity_error is not None
        raise integrity_error

    model_failed = False
    result: ExecutionResult | None = None
    try:
        result = _result_from_validated_document(document)
    except Exception:
        model_failed = True
    if model_failed or result is None:
        raise ExecutionResultIntegrityError(
            "apply.invalid_result_schema",
            "execution result could not be materialized",
        )
    return result


def load_execution_result_file(path: str | Path) -> ExecutionResult:
    """Load an execution-result artifact from a UTF-8 JSON file."""
    file_path = Path(path)
    read_failed = False
    text = ""
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError:
        read_failed = True
    if read_failed:
        raise ExecutionResultLoadError(
            "apply.invalid_syntax",
            "execution result file could not be read",
        )
    return load_execution_result_text(text)
