"""Tests for packaged governance config schema loading."""

from __future__ import annotations

from pathlib import Path

from jsonschema import Draft202012Validator

from purview_governance.config.schema import load_v1_schema, load_v3_schema
from purview_governance.config.service import validate_config_file

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE = REPO_ROOT / "examples" / "fictional-governance-config.yaml"


def test_load_v1_schema_from_package_resources() -> None:
    schema = load_v1_schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert (
        schema["$id"]
        == "https://github.com/fgnfmackk/purview-governance-automation/schemas/purview-governance-config/v1"
    )
    Draft202012Validator.check_schema(schema)


def test_load_v3_schema_from_package_resources() -> None:
    schema = load_v3_schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert (
        schema["$id"]
        == "https://github.com/fgnfmackk/purview-governance-automation/schemas/purview-governance-config/v3"
    )
    Draft202012Validator.check_schema(schema)


def test_sample_config_validates() -> None:
    config = validate_config_file(SAMPLE)
    assert config.api_version == "purview-governance-config/v1"
    assert config.target.endpoint == "https://contoso-fictional.purview.azure.com"
    assert config.authentication.strategy == "defaultAzureCredential"
    assert len(config.resources) == 1
    assert config.resources[0].name == "example-azure-storage"
    assert config.resources[0].kind == "AzureStorage"
    assert config.resources[0].endpoint == "https://azurestorage.core.windows.net/"
    assert config.resources[0].collection_reference_name == "Collection-rZX"
