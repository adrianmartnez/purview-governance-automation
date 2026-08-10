"""Sanitized apply / execution-result errors (no secrets / raw bodies)."""

from __future__ import annotations


class ApplyError(Exception):
    """Base apply failure without sensitive details."""

    def __init__(self, code: str, message: str, *, path: str = "") -> None:
        self.code = code
        self.message = message
        self.path = path
        if path:
            super().__init__(f"{code} at {path}: {message}")
        else:
            super().__init__(f"{code}: {message}")

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(code={self.code!r}, "
            f"message={self.message!r}, path={self.path!r})"
        )


class ApplyValidationError(ApplyError):
    """Raised for invalid public API input (e.g. bad mode / untrusted plan)."""


class ExecutionResultError(ApplyError):
    """Base execution-result artifact failure."""


class ExecutionResultLoadError(ExecutionResultError):
    """Raised when loading an execution-result artifact fails."""


class ExecutionResultVersionError(ExecutionResultLoadError):
    """Raised for missing or unsupported execution-result apiVersion."""


class ExecutionResultSchemaError(ExecutionResultLoadError):
    """Raised when the result document fails JSON Schema validation."""


class ExecutionResultIntegrityError(ExecutionResultLoadError):
    """Raised when schema-valid result fails semantic integrity checks."""
