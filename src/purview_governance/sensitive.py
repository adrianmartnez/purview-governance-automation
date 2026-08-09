"""Shared sensitive field-name policy (config and remote-state)."""

from __future__ import annotations

SECRET_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "clientSecret",
        "client_secret",
        "password",
        "token",
        "accessToken",
        "access_token",
        "bearerToken",
        "bearer_token",
        "privateKey",
        "private_key",
        "connectionString",
        "connection_string",
        "authorization",
        "Authorization",
        "accountKey",
        "account_key",
        "sasToken",
        "sas_token",
        "secret",
    }
)


def is_sensitive_field_name(field_name: str) -> bool:
    """Return True when ``field_name`` is a forbidden credential/secret key."""
    return field_name in SECRET_FIELD_NAMES
