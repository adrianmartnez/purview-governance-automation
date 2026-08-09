"""Minimal argparse CLI shell for purview-governance."""

from __future__ import annotations

import argparse

from purview_governance import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="purview-governance",
        description=(
            "Microsoft Purview governance automation CLI. "
            "This foundation exposes version and help only; "
            "Purview workflows are not implemented yet."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"purview-governance {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    parser.parse_args(argv)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
