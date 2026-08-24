"""Canonical UUID validation and normalization (lowercase RFC 4122 string form)."""

from __future__ import annotations

import re

UUID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def normalize_uuid_string(raw: object) -> str | None:
    """Return canonical lowercase UUID or None when raw is not a valid UUID string."""
    if not isinstance(raw, str):
        return None
    candidate = raw.strip().lower()
    if UUID_PATTERN.fullmatch(candidate) is None:
        return None
    return candidate


def require_uuid_string(raw: object, *, field_label: str = "value") -> str:
    """Validate and return canonical lowercase UUID."""
    normalized = normalize_uuid_string(raw)
    if normalized is None:
        msg = f"{field_label} must be a valid UUID string"
        raise ValueError(msg)
    return normalized
