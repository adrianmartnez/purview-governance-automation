"""Safe explicit apply and purview-execution-result/v1+v2+v3."""

from purview_governance.apply.errors import (
    ApplyError,
    ApplyValidationError,
    ExecutionResultError,
    ExecutionResultIntegrityError,
    ExecutionResultLoadError,
    ExecutionResultSchemaError,
    ExecutionResultVersionError,
)
from purview_governance.apply.identity import (
    RESULT_API_VERSION,
    RESULT_API_VERSION_V2,
    RESULT_API_VERSION_V3,
)
from purview_governance.apply.loader import load_execution_result_file, load_execution_result_text
from purview_governance.apply.models import (
    ExecutionFailure,
    ExecutionMode,
    ExecutionResult,
    OperationResult,
    build_execution_result_from_parts,
)
from purview_governance.apply.models_v2 import (
    ExecutionResultV2,
    OperationResultV2,
    build_execution_result_v2_from_parts,
)
from purview_governance.apply.models_v3 import (
    ExecutionResultV3,
    OperationResultV3,
    build_execution_result_v3_from_parts,
)
from purview_governance.apply.schema import (
    load_execution_result_v1_schema,
    load_execution_result_v2_schema,
    load_execution_result_v3_schema,
)
from purview_governance.apply.service import execute_governance_plan
from purview_governance.apply.service_v3 import execute_governance_plan_v3
from purview_governance.apply.summary import format_execution_result_summary

__all__ = [
    "RESULT_API_VERSION",
    "RESULT_API_VERSION_V2",
    "RESULT_API_VERSION_V3",
    "ApplyError",
    "ApplyValidationError",
    "ExecutionFailure",
    "ExecutionMode",
    "ExecutionResult",
    "ExecutionResultV2",
    "ExecutionResultV3",
    "ExecutionResultError",
    "ExecutionResultIntegrityError",
    "ExecutionResultLoadError",
    "ExecutionResultSchemaError",
    "ExecutionResultVersionError",
    "OperationResult",
    "OperationResultV2",
    "OperationResultV3",
    "build_execution_result_from_parts",
    "build_execution_result_v2_from_parts",
    "build_execution_result_v3_from_parts",
    "execute_governance_plan",
    "execute_governance_plan_v3",
    "format_execution_result_summary",
    "load_execution_result_file",
    "load_execution_result_text",
    "load_execution_result_v1_schema",
    "load_execution_result_v2_schema",
    "load_execution_result_v3_schema",
]
