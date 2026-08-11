"""Canonical finite-double normalization for wire ``number (double)`` fields."""

from __future__ import annotations

import math
from typing import Any


class FiniteDoubleError(ValueError):
    """Raised when a value is not a finite JSON/YAML number (double)."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def canonicalize_finite_double(value: object) -> float:
    """Validate and canonicalize a finite double for material compare/identity.

    Accepts JSON/YAML numbers that are not bool. Rejects bool, NaN, ±Inf,
    overflow outside IEEE-754 double range, and non-numeric types. Normalizes
    to Python ``float`` and maps ``-0.0`` to ``0.0`` so int/float wire syntax
    (``80`` vs ``80.0``) shares one identity.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FiniteDoubleError("value must be a finite number (not bool)")
    try:
        as_float = float(value)
    except OverflowError:
        raise FiniteDoubleError("value must be representable as a finite IEEE-754 double") from None
    if not math.isfinite(as_float):
        raise FiniteDoubleError("value must be a finite number (not NaN or Infinity)")
    if as_float == 0.0:
        return 0.0
    return as_float


def try_canonicalize_finite_double(value: object) -> float | None:
    """Return canonical float or ``None`` when validation fails."""
    try:
        return canonicalize_finite_double(value)
    except FiniteDoubleError:
        return None


def is_finite_number(value: Any) -> bool:
    """Return True when ``value`` is a finite non-bool number."""
    return try_canonicalize_finite_double(value) is not None
