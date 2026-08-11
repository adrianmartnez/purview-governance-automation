"""Unit tests for finite double canonicalization."""

from __future__ import annotations

import math

import pytest

from purview_governance.finite_double import FiniteDoubleError, canonicalize_finite_double


def test_int_and_float_equal() -> None:
    assert canonicalize_finite_double(80) == canonicalize_finite_double(80.0) == 80.0


def test_signed_zero() -> None:
    assert canonicalize_finite_double(-0.0) == 0.0
    assert math.copysign(1.0, canonicalize_finite_double(-0.0)) == 1.0


def test_rejects_bool_nan_inf() -> None:
    with pytest.raises(FiniteDoubleError):
        canonicalize_finite_double(True)
    with pytest.raises(FiniteDoubleError):
        canonicalize_finite_double(math.nan)
    with pytest.raises(FiniteDoubleError):
        canonicalize_finite_double(math.inf)
    with pytest.raises(FiniteDoubleError):
        canonicalize_finite_double(-math.inf)
    with pytest.raises(FiniteDoubleError):
        canonicalize_finite_double("80")
