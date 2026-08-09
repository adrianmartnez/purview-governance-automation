"""Deterministic endpoint and document normalization."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit, urlunsplit

from purview_governance.config.diagnostics import (
    ConfigDiagnostic,
    ConfigValidationError,
    json_pointer,
)
from purview_governance.config.models import (
    AuthenticationConfig,
    GovernanceConfig,
    TargetConfig,
)


def _invalid_endpoint_error(message: str) -> ConfigValidationError:
    return ConfigValidationError(
        (
            ConfigDiagnostic(
                code="config.invalid_endpoint",
                path=json_pointer("target", "endpoint"),
                message=message,
            ),
        )
    )


def normalize_endpoint(raw_endpoint: object) -> str:
    """Normalize and validate a Purview target endpoint string."""
    path = json_pointer("target", "endpoint")
    if not isinstance(raw_endpoint, str) or not raw_endpoint.strip():
        raise _invalid_endpoint_error("endpoint must be a non-empty string")

    endpoint = raw_endpoint.strip()
    try:
        parts = urlsplit(endpoint)
        hostname = parts.hostname
        port = parts.port
    except ValueError:
        # Invalid host/port/brackets must not escape as raw ValueError.
        raise _invalid_endpoint_error("endpoint is not a valid https URL") from None

    diagnostics: list[ConfigDiagnostic] = []
    if parts.scheme.lower() != "https":
        diagnostics.append(
            ConfigDiagnostic(
                code="config.invalid_endpoint",
                path=path,
                message="endpoint must use https",
            )
        )
    if not hostname:
        diagnostics.append(
            ConfigDiagnostic(
                code="config.invalid_endpoint",
                path=path,
                message="endpoint must include a hostname",
            )
        )
    if parts.username is not None or parts.password is not None:
        diagnostics.append(
            ConfigDiagnostic(
                code="config.invalid_endpoint",
                path=path,
                message="endpoint must not include userinfo",
            )
        )
    if parts.query:
        diagnostics.append(
            ConfigDiagnostic(
                code="config.invalid_endpoint",
                path=path,
                message="endpoint must not include a query string",
            )
        )
    if parts.fragment:
        diagnostics.append(
            ConfigDiagnostic(
                code="config.invalid_endpoint",
                path=path,
                message="endpoint must not include a fragment",
            )
        )

    path_part = parts.path or ""
    if path_part not in {"", "/"}:
        diagnostics.append(
            ConfigDiagnostic(
                code="config.invalid_endpoint",
                path=path,
                message="endpoint must not include a path",
            )
        )

    if diagnostics:
        raise ConfigValidationError(diagnostics)

    assert hostname is not None  # for type checkers
    host = hostname.lower()
    netloc = host
    if port is not None:
        netloc = f"{host}:{port}"
    return urlunsplit(("https", netloc, "", "", ""))


def normalize_document(document: dict[str, Any]) -> GovernanceConfig:
    """Build an immutable normalized config from a validated document."""
    endpoint = normalize_endpoint(document["target"]["endpoint"])
    return GovernanceConfig(
        api_version=str(document["apiVersion"]),
        target=TargetConfig(endpoint=endpoint),
        authentication=AuthenticationConfig(strategy=str(document["authentication"]["strategy"])),
        resources=tuple(document.get("resources") or ()),
    )
