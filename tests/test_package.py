"""Package import and version contract tests."""

from __future__ import annotations

import importlib.metadata
import subprocess
import sys

import purview_governance


def test_package_version_literal() -> None:
    assert purview_governance.__version__ == "1.0.0"


def test_distribution_metadata_matches_runtime() -> None:
    dist_version = importlib.metadata.version("purview-governance-automation")
    assert dist_version == purview_governance.__version__ == "1.0.0"


def test_module_entry_help() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "purview_governance", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "purview-governance" in result.stdout


def test_module_entry_version() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "purview_governance", "--version"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "purview-governance 1.0.0"
