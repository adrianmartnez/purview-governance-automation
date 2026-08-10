"""Canonical JSON serialization and observed-state safety identity."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def dumps_canonical(document: dict[str, Any]) -> str:
    """Serialize a plain JSON document to deterministic canonical JSON text.

    Convention matches governance config canonicalization: UTF-8 text with
    sorted keys, compact separators, ``ensure_ascii=False``, ``allow_nan=False``,
    and no trailing newline.
    """
    return dumps_canonical_value(document)


def dumps_canonical_value(value: object) -> str:
    """Serialize any JSON value to deterministic canonical JSON text."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def canonical_json_scalar(value: object) -> str:
    """Unambiguous JSON canonical encoding for a scalar or structured value.

    Distinguishes Python ``None`` (``null``) from ``""`` (JSON empty string).
    """
    return dumps_canonical_value(value)


def compute_value_identity(value: object) -> str:
    """Return ``sha256:<hex>`` of UTF-8 canonical JSON for a typed value.

    Callers must run ``reject_sensitive_keys`` on the value subtree first.
    """
    digest = hashlib.sha256(dumps_canonical_value(value).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def compute_material_state_identity(identity_document: dict[str, Any]) -> str:
    """Return ``sha256:<hex>`` for the identity document (must omit the identity field)."""
    if "materialStateIdentity" in identity_document:
        msg = "identity document must not contain materialStateIdentity"
        raise ValueError(msg)
    canonical_bytes = dumps_canonical(identity_document).encode("utf-8")
    digest = hashlib.sha256(canonical_bytes).hexdigest()
    return f"sha256:{digest}"
