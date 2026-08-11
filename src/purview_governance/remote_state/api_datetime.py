"""Lightweight Scanning API date-time validation (stdlib only)."""

from __future__ import annotations

from datetime import datetime


def validate_api_datetime_string(value: object) -> str:
    """Validate a published ``string (date-time)`` wire value.

    Requires an explicit timezone (``Z`` or numeric offset). Accepts official
    sample forms with ``Z`` and fractional seconds beyond six digits by
    truncating only for parsing (the original string is returned unchanged).
    """
    if not isinstance(value, str):
        raise ValueError("date-time must be a string")
    raw = value
    if not raw:
        raise ValueError("date-time must not be empty")

    parse_text = raw
    if parse_text.endswith(("Z", "z")):
        parse_text = parse_text[:-1] + "+00:00"

    # Truncate fractional seconds to microseconds for datetime.fromisoformat.
    # Keep timezone suffix intact.
    if "." in parse_text:
        head, rest = parse_text.split(".", 1)
        digits = []
        idx = 0
        while idx < len(rest) and rest[idx].isdigit():
            digits.append(rest[idx])
            idx += 1
        if not digits:
            raise ValueError("date-time fractional seconds are malformed")
        fraction = "".join(digits[:6]).ljust(6, "0")
        suffix = rest[idx:]
        parse_text = f"{head}.{fraction}{suffix}"

    try:
        parsed = datetime.fromisoformat(parse_text)
    except ValueError as exc:
        raise ValueError("date-time is not a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("date-time must include an explicit timezone")
    return raw
