"""Sanitized governance-plan errors (no secrets / raw plan bodies)."""

from __future__ import annotations


class PlanError(Exception):
    """Base plan failure without sensitive details."""

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


class PlanBuildError(PlanError):
    """Raised when building a plan from untrusted public inputs fails."""


class PlanLoadError(PlanError):
    """Raised when loading a plan artifact fails."""


class PlanVersionError(PlanLoadError):
    """Raised for missing or unsupported plan apiVersion."""


class PlanSchemaError(PlanLoadError):
    """Raised when the plan document fails JSON Schema validation."""


class PlanIntegrityError(PlanLoadError):
    """Raised when schema-valid plan fails semantic/canonical integrity checks."""
