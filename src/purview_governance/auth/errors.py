"""Sanitized authentication errors (no credential material)."""

from __future__ import annotations


class AuthenticationError(Exception):
    """Public authentication failure without sensitive details."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")

    def __repr__(self) -> str:
        return f"AuthenticationError(code={self.code!r}, message={self.message!r})"
