"""Internal path safety helpers for CLI artifact I/O."""

from __future__ import annotations

import os
from pathlib import Path


def resolve_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def paths_conflict(left: str | Path, right: str | Path) -> bool:
    """Return True when two paths refer to the same filesystem location."""
    a = resolve_path(left)
    b = resolve_path(right)
    if os.name == "nt":
        if str(a).casefold() == str(b).casefold():
            return True
    elif a == b:
        return True
    if a.exists() and b.exists():
        samefile_failed = False
        try:
            return os.path.samefile(a, b)
        except OSError:
            samefile_failed = True
        if samefile_failed:
            return False
    return False
