"""Strict JSON/YAML loading with duplicate-key rejection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from purview_governance.config.diagnostics import (
    ConfigDiagnostic,
    ConfigValidationError,
    json_pointer,
)


class DuplicateKeyError(ValueError):
    """Internal signal that a mapping contains a duplicated key."""

    def __init__(self, path: str, key: object) -> None:
        self.path = path
        self.key = key
        super().__init__(f"duplicate key {key!r} at {path}")


class InvalidMappingKeyError(ValueError):
    """Internal signal that a mapping key is not a string."""


def _raise_duplicate(path: str, key: object) -> None:
    raise DuplicateKeyError(path, key)


def _object_pairs_hook(pairs: list[tuple[Any, Any]]) -> dict[Any, Any]:
    result: dict[Any, Any] = {}
    for key, value in pairs:
        if key in result:
            _raise_duplicate(json_pointer(key), key)
        result[key] = value
    return result


class StrictSafeLoader(yaml.SafeLoader):
    """SafeLoader subclass that rejects duplicate mapping keys and non-string keys."""


def _construct_mapping(loader: yaml.SafeLoader, node: yaml.nodes.MappingNode) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=False)
        if not isinstance(key, str):
            raise InvalidMappingKeyError("configuration mapping keys must be strings")
        if key in mapping:
            _raise_duplicate(json_pointer(key), key)
        mapping[key] = loader.construct_object(value_node, deep=False)
    return mapping


StrictSafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping,
)


def _duplicate_diagnostics(exc: DuplicateKeyError) -> tuple[ConfigDiagnostic, ...]:
    return (
        ConfigDiagnostic(
            code="config.duplicate_key",
            path=exc.path,
            message=f"duplicate key {exc.key!r} is not allowed",
        ),
    )


def _syntax_diagnostics(message: str) -> tuple[ConfigDiagnostic, ...]:
    return (
        ConfigDiagnostic(
            code="config.invalid_syntax",
            path="",
            message=message,
        ),
    )


def load_json_text(text: str) -> dict[str, Any]:
    """Parse JSON text rejecting duplicate object keys."""
    try:
        document = json.loads(text, object_pairs_hook=_object_pairs_hook)
    except DuplicateKeyError as exc:
        raise ConfigValidationError(_duplicate_diagnostics(exc)) from None
    except json.JSONDecodeError as exc:
        raise ConfigValidationError(_syntax_diagnostics(f"invalid JSON: {exc.msg}")) from None
    if not isinstance(document, dict):
        raise ConfigValidationError(
            (
                ConfigDiagnostic(
                    code="config.invalid_syntax",
                    path="",
                    message="configuration document must be a JSON object",
                ),
            )
        )
    return document


def load_yaml_text(text: str) -> dict[str, Any]:
    """Parse YAML text with SafeLoader semantics and duplicate-key rejection."""
    try:
        document = yaml.load(text, Loader=StrictSafeLoader)  # noqa: S506 — SafeLoader subclass
    except DuplicateKeyError as exc:
        raise ConfigValidationError(_duplicate_diagnostics(exc)) from None
    except InvalidMappingKeyError:
        raise ConfigValidationError(
            _syntax_diagnostics("configuration mapping keys must be strings")
        ) from None
    except TypeError:
        # Non-hashable mapping keys must not escape as raw TypeError.
        raise ConfigValidationError(
            _syntax_diagnostics("configuration mapping keys must be strings")
        ) from None
    except yaml.YAMLError:
        raise ConfigValidationError(_syntax_diagnostics("invalid YAML: YAMLError")) from None
    if document is None:
        raise ConfigValidationError(
            (
                ConfigDiagnostic(
                    code="config.invalid_syntax",
                    path="",
                    message="configuration document must not be empty",
                ),
            )
        )
    if not isinstance(document, dict):
        raise ConfigValidationError(
            (
                ConfigDiagnostic(
                    code="config.invalid_syntax",
                    path="",
                    message="configuration document must be a YAML mapping",
                ),
            )
        )
    return document


def load_config_text(text: str, *, format_hint: str) -> dict[str, Any]:
    """Load a configuration document from text using an explicit format hint."""
    normalized = format_hint.lower()
    if normalized == "json":
        return load_json_text(text)
    if normalized in {"yaml", "yml"}:
        return load_yaml_text(text)
    raise ConfigValidationError(
        (
            ConfigDiagnostic(
                code="config.invalid_syntax",
                path="",
                message=f"unsupported configuration format: {format_hint}",
            ),
        )
    )


def load_config_file(path: str | Path) -> dict[str, Any]:
    """Load a configuration file, inferring JSON vs YAML from the suffix."""
    file_path = Path(path)
    suffix = file_path.suffix.lower()
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigValidationError(
            (
                ConfigDiagnostic(
                    code="config.invalid_syntax",
                    path="",
                    message=f"unable to read configuration file: {exc.strerror or exc}",
                ),
            )
        ) from None

    if suffix == ".json":
        return load_json_text(text)
    if suffix in {".yaml", ".yml"}:
        return load_yaml_text(text)
    raise ConfigValidationError(
        (
            ConfigDiagnostic(
                code="config.invalid_syntax",
                path="",
                message=("unsupported configuration file extension; use .json, .yaml, or .yml"),
            ),
        )
    )
