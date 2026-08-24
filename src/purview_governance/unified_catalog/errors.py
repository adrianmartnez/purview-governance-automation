"""Sanitized Unified Catalog client errors (no secrets / raw bodies)."""

from __future__ import annotations


class UnifiedCatalogClientError(Exception):
    """Base public client failure without sensitive details."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.code!r}, message={self.message!r})"


class UnifiedCatalogCompatibilityError(UnifiedCatalogClientError):
    """Unsupported API version or incompatible Unified Catalog surface."""


class UnifiedCatalogRequestError(UnifiedCatalogClientError):
    """Transport or connection failure before a usable HTTP response."""


class UnifiedCatalogTimeoutError(UnifiedCatalogClientError):
    """Bounded connect/read/write/pool timeout."""


class UnifiedCatalogRequestBuildError(UnifiedCatalogClientError):
    """Invalid input while constructing a request."""


class UnifiedCatalogHttpError(UnifiedCatalogClientError):
    """Non-success HTTP status (including 3xx and undocumented 2xx)."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int,
        method: str | None = None,
        path: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.method = method
        self.path = path
        super().__init__(code, message)

    def __repr__(self) -> str:
        return (
            f"UnifiedCatalogHttpError(code={self.code!r}, message={self.message!r}, "
            f"status_code={self.status_code!r}, method={self.method!r}, "
            f"path={self.path!r})"
        )


class UnifiedCatalogResponseError(UnifiedCatalogClientError):
    """Invalid JSON or response contract shape."""


class UnifiedCatalogPaginationError(UnifiedCatalogClientError):
    """Unsafe or invalid pagination link / page bound."""
