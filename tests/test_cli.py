"""Unit tests for the argparse CLI foundation."""

from __future__ import annotations

import pytest

from purview_governance.cli import build_parser, main


def test_build_parser_help_mentions_prog() -> None:
    parser = build_parser()
    help_text = parser.format_help()
    assert "purview-governance" in help_text
    assert "--version" in help_text


def test_main_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert "purview-governance" in captured.out


def test_main_version_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "purview-governance 1.1.0"


def test_main_unknown_argument_exits_two() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--definitely-not-a-flag"])
    assert excinfo.value.code == 2


def test_main_no_args_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    captured = capsys.readouterr()
    assert "usage:" in captured.out
