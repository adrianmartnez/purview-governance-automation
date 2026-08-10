"""argparse CLI for purview-governance v1 workflows."""

from __future__ import annotations

import argparse
import contextlib
import os
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from typing import TextIO

from purview_governance import __version__
from purview_governance.apply import (
    ApplyValidationError,
    ExecutionMode,
    ExecutionResult,
    ExecutionResultError,
    execute_governance_plan,
    format_execution_result_summary,
    load_execution_result_file,
)
from purview_governance.auth import create_default_azure_credential_provider
from purview_governance.auth.errors import AuthenticationError
from purview_governance.cli_paths import paths_conflict, resolve_path
from purview_governance.config import validate_config_file
from purview_governance.config.diagnostics import ConfigValidationError
from purview_governance.config.models import CONFIG_API_VERSION_V2
from purview_governance.plan import (
    PlanError,
    build_governance_plan,
    build_governance_plan_v2,
    format_plan_summary,
    load_plan_file,
)
from purview_governance.remote_state import capture_remote_state, capture_remote_state_v2
from purview_governance.remote_state.canonical import dumps_canonical
from purview_governance.remote_state.errors import RemoteStateError
from purview_governance.scanning import PurviewScanningClient
from purview_governance.scanning.errors import PurviewClientError

EXIT_SUCCESS = 0
EXIT_USAGE = 2
EXIT_VALIDATION = 3
EXIT_SAFETY = 4
EXIT_PREWRITE = 5
EXIT_WRITE = 6
EXIT_PERSIST = 7


@dataclass(frozen=True, slots=True)
class _CliDependencies:
    """Package-private injectable dependencies (not a public CLI surface)."""

    scanning_client_factory: Callable[[str], PurviewScanningClient] | None = None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="purview-governance",
        description=(
            "Microsoft Purview governance automation CLI. "
            "Dry-run is the default for apply; mutation requires --apply."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"purview-governance {__version__}",
    )
    sub = parser.add_subparsers(dest="command")

    config_parser = sub.add_parser("config", help="Configuration workflows")
    config_sub = config_parser.add_subparsers(dest="config_command", required=True)
    config_validate = config_sub.add_parser("validate", help="Validate a governance config file")
    config_validate.add_argument("config")
    config_validate.add_argument("--json", action="store_true", dest="as_json")

    remote_parser = sub.add_parser("remote-state", help="Remote-state workflows")
    remote_sub = remote_parser.add_subparsers(dest="remote_command", required=True)
    remote_capture = remote_sub.add_parser("capture", help="Capture read-only remote state")
    remote_capture.add_argument("config")
    remote_capture.add_argument("--output", required=True)
    remote_capture.add_argument("--force", action="store_true")

    plan_parser = sub.add_parser("plan", help="Plan workflows")
    plan_sub = plan_parser.add_subparsers(dest="plan_command", required=True)
    plan_create = plan_sub.add_parser(
        "create", help="Create a governance plan from live remote state"
    )
    plan_create.add_argument("config")
    plan_create.add_argument("--output", required=True)
    plan_create.add_argument("--force", action="store_true")
    plan_inspect = plan_sub.add_parser("inspect", help="Inspect a saved governance plan")
    plan_inspect.add_argument("plan")
    plan_inspect.add_argument("--json", action="store_true", dest="as_json")

    apply_parser = sub.add_parser("apply", help="Dry-run or explicitly apply a saved plan")
    apply_parser.add_argument("plan")
    apply_parser.add_argument(
        "--apply",
        action="store_true",
        dest="authorize_apply",
        help="Explicitly authorize remote mutation (default is dry-run)",
    )
    apply_parser.add_argument("--result", dest="result_path")
    apply_parser.add_argument("--force", action="store_true")
    apply_parser.add_argument("--json", action="store_true", dest="as_json")

    result_parser = sub.add_parser("result", help="Execution-result workflows")
    result_sub = result_parser.add_subparsers(dest="result_command", required=True)
    result_inspect = result_sub.add_parser("inspect", help="Inspect a saved execution result")
    result_inspect.add_argument("result")
    result_inspect.add_argument("--json", action="store_true", dest="as_json")

    return parser


def main(argv: list[str] | None = None) -> int:
    """Public console entrypoint (no injectable transport override)."""
    return _run(argv)


def _run(argv: list[str] | None = None, *, deps: _CliDependencies | None = None) -> int:
    """Package-private dispatcher used by tests for dependency injection."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not getattr(args, "command", None):
        parser.print_help()
        return EXIT_SUCCESS

    dependencies = deps or _CliDependencies()
    return _dispatch(args, dependencies)


def _dispatch(args: argparse.Namespace, deps: _CliDependencies) -> int:
    if args.command == "config" and args.config_command == "validate":
        return _cmd_config_validate(args)
    if args.command == "remote-state" and args.remote_command == "capture":
        return _cmd_remote_capture(args, deps)
    if args.command == "plan" and args.plan_command == "create":
        return _cmd_plan_create(args, deps)
    if args.command == "plan" and args.plan_command == "inspect":
        return _cmd_plan_inspect(args)
    if args.command == "apply":
        return _cmd_apply(args, deps)
    if args.command == "result" and args.result_command == "inspect":
        return _cmd_result_inspect(args)
    return EXIT_USAGE


def _cmd_config_validate(args: argparse.Namespace) -> int:
    try:
        config = validate_config_file(args.config)
    except ConfigValidationError as exc:
        return _print_error(exc.code, EXIT_VALIDATION)
    except OSError:
        return _print_error("cli.input_not_found", EXIT_VALIDATION)
    if args.as_json:
        print(dumps_canonical({"status": "valid", "apiVersion": config.api_version}))
    else:
        print("config valid")
    return EXIT_SUCCESS


def _cmd_remote_capture(args: argparse.Namespace, deps: _CliDependencies) -> int:
    try:
        _validate_output_vs_input(args.config, args.output, force=args.force)
        config = validate_config_file(args.config)
    except ConfigValidationError as exc:
        return _print_error(exc.code, EXIT_VALIDATION)
    except _CliLocalError as exc:
        return _print_error(exc.code, EXIT_VALIDATION)
    except OSError:
        return _print_error("cli.input_not_found", EXIT_VALIDATION)

    client = None
    try:
        client = _build_client(config.target.endpoint, deps)
        if config.api_version == CONFIG_API_VERSION_V2:
            remote = capture_remote_state_v2(client)
        else:
            remote = capture_remote_state(client)
        _write_atomic(args.output, dumps_canonical(remote.to_document()), force=args.force)
    except AuthenticationError:
        return _print_error("cli.authentication_failed", EXIT_PREWRITE)
    except (RemoteStateError, PurviewClientError):
        return _print_error("cli.remote_read_failed", EXIT_PREWRITE)
    except _CliLocalError as exc:
        return _print_error(
            exc.code, EXIT_PERSIST if exc.code == "cli.result_persist_failed" else EXIT_VALIDATION
        )
    finally:
        if client is not None:
            client.close()
    return EXIT_SUCCESS


def _cmd_plan_create(args: argparse.Namespace, deps: _CliDependencies) -> int:
    try:
        _validate_output_vs_input(args.config, args.output, force=args.force)
        config = validate_config_file(args.config)
    except ConfigValidationError as exc:
        return _print_error(exc.code, EXIT_VALIDATION)
    except _CliLocalError as exc:
        return _print_error(exc.code, EXIT_VALIDATION)
    except OSError:
        return _print_error("cli.input_not_found", EXIT_VALIDATION)

    client = None
    try:
        client = _build_client(config.target.endpoint, deps)
        if config.api_version == CONFIG_API_VERSION_V2:
            remote = capture_remote_state_v2(client)
            plan = build_governance_plan_v2(config, remote)
        else:
            remote = capture_remote_state(client)
            plan = build_governance_plan(config, remote)
        _write_atomic(args.output, plan.to_canonical_json(), force=args.force)
        print(format_plan_summary(plan), end="")
    except AuthenticationError:
        return _print_error("cli.authentication_failed", EXIT_PREWRITE)
    except (RemoteStateError, PurviewClientError):
        return _print_error("cli.remote_read_failed", EXIT_PREWRITE)
    except PlanError:
        return _print_error("cli.plan_build_failed", EXIT_VALIDATION)
    except _CliLocalError as exc:
        return _print_error(
            exc.code, EXIT_PERSIST if exc.code == "cli.result_persist_failed" else EXIT_VALIDATION
        )
    finally:
        if client is not None:
            client.close()
    return EXIT_SUCCESS


def _cmd_plan_inspect(args: argparse.Namespace) -> int:
    try:
        plan = load_plan_file(args.plan)
    except PlanError as exc:
        return _print_error(exc.code, EXIT_VALIDATION)
    except OSError:
        return _print_error("cli.input_not_found", EXIT_VALIDATION)
    if args.as_json:
        print(plan.to_canonical_json())
    else:
        print(format_plan_summary(plan), end="")
    return EXIT_SUCCESS


def _cmd_apply(args: argparse.Namespace, deps: _CliDependencies) -> int:
    result_path = args.result_path
    try:
        if result_path:
            _validate_output_vs_input(args.plan, result_path, force=args.force)
            _preflight_output_destination(result_path, force=args.force)
        plan = load_plan_file(args.plan)
    except PlanError as exc:
        return _print_error(exc.code, EXIT_VALIDATION)
    except _CliLocalError as exc:
        return _print_error(exc.code, EXIT_VALIDATION)
    except OSError:
        return _print_error("cli.input_not_found", EXIT_VALIDATION)

    mode = ExecutionMode.APPLY if args.authorize_apply else ExecutionMode.DRY_RUN
    client = None
    result: ExecutionResult | None = None
    try:
        client = _build_client(plan.target_context.endpoint, deps)
        result = execute_governance_plan(plan, client, mode=mode)
    except ApplyValidationError as exc:
        return _print_error(exc.code, EXIT_VALIDATION)
    except AuthenticationError:
        return _print_error("cli.authentication_failed", EXIT_PREWRITE)
    except Exception:
        # Unexpected escape from the service: never claim pre-write if APPLY may
        # have already mutated. Dry-run never PUTs, so EXIT_PREWRITE is safe.
        if mode is ExecutionMode.APPLY:
            return _print_error("cli.apply_internal_failure", EXIT_WRITE)
        return _print_error("cli.apply_failed", EXIT_PREWRITE)
    finally:
        if client is not None:
            client.close()

    assert result is not None
    persist_failed = False
    if result_path:
        try:
            _write_atomic(result_path, result.to_canonical_json(), force=args.force)
        except _CliLocalError:
            persist_failed = True

    exit_code = _exit_for_result(result)
    if args.as_json:
        print(result.to_canonical_json())
    else:
        print(format_execution_result_summary(result), end="")

    if persist_failed:
        _print_error("cli.result_persist_failed", EXIT_PERSIST)
        return EXIT_PERSIST
    return exit_code


def _cmd_result_inspect(args: argparse.Namespace) -> int:
    try:
        result = load_execution_result_file(args.result)
    except ExecutionResultError as exc:
        return _print_error(exc.code, EXIT_VALIDATION)
    except OSError:
        return _print_error("cli.input_not_found", EXIT_VALIDATION)
    if args.as_json:
        print(result.to_canonical_json())
    else:
        print(format_execution_result_summary(result), end="")
    return EXIT_SUCCESS


def _build_client(endpoint: str, deps: _CliDependencies) -> PurviewScanningClient:
    if deps.scanning_client_factory is not None:
        return deps.scanning_client_factory(endpoint)
    provider = create_default_azure_credential_provider()
    return PurviewScanningClient(endpoint, provider)


def _exit_for_result(result: ExecutionResult) -> int:
    if result.status in {"dry-run-ready", "applied"}:
        return EXIT_SUCCESS
    if result.status in {"blocked", "wrong-target", "stale"}:
        return EXIT_SAFETY
    if result.status == "failed-before-write":
        return EXIT_PREWRITE
    if result.status in {"write-failed", "indeterminate"}:
        return EXIT_WRITE
    return EXIT_VALIDATION


class _CliLocalError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _validate_output_vs_input(input_path: str, output_path: str, *, force: bool) -> None:
    if paths_conflict(input_path, output_path):
        raise _CliLocalError("cli.output_aliases_input")
    _preflight_output_destination(output_path, force=force)


def _preflight_output_destination(output_path: str, *, force: bool) -> None:
    out = resolve_path(output_path)
    parent = out.parent
    if not parent.exists() or not parent.is_dir():
        raise _CliLocalError("cli.output_parent_invalid")
    if out.exists() and out.is_dir():
        raise _CliLocalError("cli.output_is_directory")
    if out.exists() and not force:
        raise _CliLocalError("cli.output_exists")


def _write_atomic(output_path: str, content: str, *, force: bool) -> None:
    out = resolve_path(output_path)
    if out.exists() and out.is_dir():
        raise _CliLocalError("cli.output_is_directory")
    if out.exists() and not force:
        raise _CliLocalError("cli.output_exists")
    parent = out.parent
    fd = None
    tmp_name = None
    write_failed = False
    try:
        fd, tmp_name = tempfile.mkstemp(prefix=f".{out.name}.", suffix=".tmp", dir=str(parent))
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            fd = None
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, out)
        tmp_name = None
    except OSError:
        write_failed = True
    finally:
        if fd is not None:
            with contextlib.suppress(OSError):
                os.close(fd)
        if tmp_name is not None:
            with contextlib.suppress(OSError):
                os.unlink(tmp_name)
    if write_failed:
        raise _CliLocalError("cli.result_persist_failed")


def _print_error(code: str, exit_code: int, *, stream: TextIO | None = None) -> int:
    out = sys.stderr if stream is None else stream
    print(code, file=out)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
