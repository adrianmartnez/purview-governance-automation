"""Normalized governance configuration models."""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TargetConfig:
    endpoint: str


@dataclass(frozen=True, slots=True)
class AuthenticationConfig:
    strategy: str


@dataclass(frozen=True, slots=True)
class GovernanceConfig:
    """Deterministic normalized governance configuration (contract v1)."""

    api_version: str
    target: TargetConfig
    authentication: AuthenticationConfig
    resources: tuple[object, ...] = ()

    def to_document(self) -> dict[str, object]:
        """Return the canonical document shape used for serialization."""
        return {
            "apiVersion": self.api_version,
            "authentication": {"strategy": self.authentication.strategy},
            "resources": list(self.resources),
            "target": {"endpoint": self.target.endpoint},
        }


def to_canonical_json(config: GovernanceConfig) -> str:
    """Serialize normalized config to deterministic canonical JSON."""
    return json.dumps(
        config.to_document(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
