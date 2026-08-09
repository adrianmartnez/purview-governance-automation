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
    DataSourceResourceConfig,
    GovernanceConfig,
    TargetConfig,
)
from purview_governance.data_source_endpoint import (
    DataSourceEndpointError,
    validate_data_source_endpoint,
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


def _normalize_data_source_resource(
    raw: object,
    *,
    index: int,
) -> DataSourceResourceConfig:
    path_base = ("resources", index)
    if not isinstance(raw, dict):
        raise ConfigValidationError(
            (
                ConfigDiagnostic(
                    code="config.invalid_syntax",
                    path=json_pointer(*path_base),
                    message="resource must be an object",
                ),
            )
        )
    # Name constraints are enforced by the packaged JSON Schema (dataSourceName).
    name = str(raw["name"])

    props = raw["properties"]
    if not isinstance(props, dict):
        raise ConfigValidationError(
            (
                ConfigDiagnostic(
                    code="config.invalid_syntax",
                    path=json_pointer(*path_base, "properties"),
                    message="properties must be an object",
                ),
            )
        )
    endpoint_raw = props["endpoint"]
    endpoint_failed = False
    endpoint: str | None = None
    try:
        endpoint = validate_data_source_endpoint(endpoint_raw)
    except DataSourceEndpointError:
        endpoint_failed = True
    if endpoint_failed or endpoint is None:
        raise ConfigValidationError(
            (
                ConfigDiagnostic(
                    code="config.invalid_data_source_endpoint",
                    path=json_pointer(*path_base, "properties", "endpoint"),
                    message="Data Source endpoint is invalid or unsafe",
                ),
            )
        ) from None
    collection = props["collection"]
    if not isinstance(collection, dict):
        raise ConfigValidationError(
            (
                ConfigDiagnostic(
                    code="config.invalid_syntax",
                    path=json_pointer(*path_base, "properties", "collection"),
                    message="collection must be an object",
                ),
            )
        )
    ref = collection["referenceName"]
    if not isinstance(ref, str) or not ref.strip():
        raise ConfigValidationError(
            (
                ConfigDiagnostic(
                    code="config.invalid_syntax",
                    path=json_pointer(*path_base, "properties", "collection", "referenceName"),
                    message="collection.referenceName must be a non-empty string",
                ),
            )
        )
    return DataSourceResourceConfig(
        name=name,
        kind=str(raw["kind"]),
        endpoint=endpoint,
        collection_reference_name=ref.strip(),
    )


def normalize_document(document: dict[str, Any]) -> GovernanceConfig:
    """Build an immutable normalized config from a validated document."""
    endpoint = normalize_endpoint(document["target"]["endpoint"])
    raw_resources = document.get("resources") or ()
    resources = tuple(
        _normalize_data_source_resource(item, index=index)
        for index, item in enumerate(raw_resources)
    )
    # Deterministic order by name (independent of YAML/JSON array order).
    resources = tuple(sorted(resources, key=lambda item: item.name))
    return GovernanceConfig(
        api_version=str(document["apiVersion"]),
        target=TargetConfig(endpoint=endpoint),
        authentication=AuthenticationConfig(strategy=str(document["authentication"]["strategy"])),
        resources=resources,
    )
