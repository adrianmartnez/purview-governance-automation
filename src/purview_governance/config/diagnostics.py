"""Stable configuration validation diagnostics."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from purview_governance.sensitive import SECRET_FIELD_NAMES

# Re-export for existing imports.
__all__ = [
    "SECRET_FIELD_NAMES",
    "ConfigDiagnostic",
    "ConfigValidationError",
    "classify_unknown_field",
    "json_pointer",
]


@dataclass(frozen=True, slots=True)
class ConfigDiagnostic:
    """A single stable, reviewable configuration diagnostic."""

    code: str
    path: str
    message: str


class ConfigValidationError(Exception):
    """Raised when governance configuration fails validation."""

    def __init__(self, diagnostics: Iterable[ConfigDiagnostic]) -> None:
        self.diagnostics = tuple(sorted(diagnostics, key=_diagnostic_sort_key))
        if not self.diagnostics:
            msg = "configuration validation failed"
        elif len(self.diagnostics) == 1:
            d = self.diagnostics[0]
            msg = f"{d.code} at {d.path}: {d.message}"
        else:
            msg = f"configuration validation failed with {len(self.diagnostics)} diagnostics"
        super().__init__(msg)


def _diagnostic_sort_key(diagnostic: ConfigDiagnostic) -> tuple[str, str, str]:
    return (diagnostic.path, diagnostic.code, diagnostic.message)


def classify_unknown_field(field_name: str) -> str:
    """Map an unknown property name to a stable diagnostic code."""
    if field_name in SECRET_FIELD_NAMES:
        return "config.secret_field_forbidden"
    return "config.unknown_field"


def json_pointer(*parts: object) -> str:
    """Build a JSON Pointer from path segments."""
    if not parts:
        return ""
    escaped = []
    for part in parts:
        text = str(part).replace("~", "~0").replace("/", "~1")
        escaped.append(text)
    return "/" + "/".join(escaped)
