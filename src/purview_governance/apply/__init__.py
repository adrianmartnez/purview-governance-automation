"""Safe explicit Data Source apply and purview-execution-result/v1."""

from purview_governance.apply.errors import (
    ApplyError,
    ApplyValidationError,
    ExecutionResultError,
    ExecutionResultIntegrityError,
    ExecutionResultLoadError,
    ExecutionResultSchemaError,
    ExecutionResultVersionError,
)
from purview_governance.apply.identity import RESULT_API_VERSION
from purview_governance.apply.loader import load_execution_result_file, load_execution_result_text
from purview_governance.apply.models import (
    ExecutionFailure,
    ExecutionMode,
    ExecutionResult,
    OperationResult,
    build_execution_result_from_parts,
)
from purview_governance.apply.schema import load_execution_result_v1_schema
from purview_governance.apply.service import execute_governance_plan
from purview_governance.apply.summary import format_execution_result_summary

__all__ = [
    "RESULT_API_VERSION",
    "ApplyError",
    "ApplyValidationError",
    "ExecutionFailure",
    "ExecutionMode",
    "ExecutionResult",
    "ExecutionResultError",
    "ExecutionResultIntegrityError",
    "ExecutionResultLoadError",
    "ExecutionResultSchemaError",
    "ExecutionResultVersionError",
    "OperationResult",
    "build_execution_result_from_parts",
    "execute_governance_plan",
    "format_execution_result_summary",
    "load_execution_result_file",
    "load_execution_result_text",
    "load_execution_result_v1_schema",
]
