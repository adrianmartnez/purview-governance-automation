"""Sanitized remote-state capture errors (no secrets / raw bodies)."""

from __future__ import annotations


class RemoteStateError(Exception):
    """Fail-closed remote-state capture failure without sensitive details."""

    def __init__(self, code: str, message: str, *, path: str = "") -> None:
        self.code = code
        self.message = message
        self.path = path
        if path:
            super().__init__(f"{code} at {path}: {message}")
        else:
            super().__init__(f"{code}: {message}")

    def __repr__(self) -> str:
        return f"RemoteStateError(code={self.code!r}, message={self.message!r}, path={self.path!r})"
