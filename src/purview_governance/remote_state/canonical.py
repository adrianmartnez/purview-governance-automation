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
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def compute_material_state_identity(identity_document: dict[str, Any]) -> str:
    """Return ``sha256:<hex>`` for the identity document (must omit the identity field)."""
    if "materialStateIdentity" in identity_document:
        msg = "identity document must not contain materialStateIdentity"
        raise ValueError(msg)
    canonical_bytes = dumps_canonical(identity_document).encode("utf-8")
    digest = hashlib.sha256(canonical_bytes).hexdigest()
    return f"sha256:{digest}"
