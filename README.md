# purview-governance-automation

[![CI](https://github.com/fgnfmackk/purview-governance-automation/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/fgnfmackk/purview-governance-automation/actions/workflows/ci.yml)

Microsoft Purview governance automation in Python for deterministic Data Map
Data Source planning and safe explicit apply workflows.

Stable package version: `1.0.0` (v1.0 released / stable).

`main` develops toward **v1.1** as package `1.1.0.dev0` (Scans, Custom Scan
Rule Sets, and Custom Classification Rules: config/remote/diff/plan/apply v2).
Controlled multi-resource apply accepts plan/v2 with dry-run default; plan/v1
apply and execution-result/v1 remain frozen. No automatic deletes. Explicit
unsupported Scan configurables block safe comparison. No live-tenant validation
claim.

Package SemVer is independent of machine-contract versions
(`purview-governance-config/v1`, `purview-remote-state/v1`,
`purview-governance-plan/v1`, `purview-execution-result/v1`). See
[CHANGELOG.md](CHANGELOG.md).

## Status

### Implemented

- installable Python package (`src/` layout, wheel/sdist) and five CI gates:
  `lint`, `unit-tests`, `package-validation`, `api-contract-tests`, `cli-integration`
- versioned config `purview-governance-config/v1` (AzureStorage vertical slice)
- Microsoft Entra auth boundary (`DefaultAzureCredential`, scope
  `https://purview.azure.net/.default`)
- Scanning Data Plane client pinned to API version `2023-09-01` (list/get +
  package-private create-or-replace receipt)
- deterministic loopback contract-test server
- read-only remote-state `purview-remote-state/v1`
- desired-vs-remote diff (create/replace/no-op/remote-only/blocked; no delete)
- versioned plan `purview-governance-plan/v1` and `/v2`
- safe explicit apply (`execute_governance_plan`) with dry-run default
  (plan/v1 → execution-result/v1; plan/v2 → execution-result/v2)
- execution result `purview-execution-result/v1` (frozen) and `/v2`
- complete v1 CLI workflows (apply accepts plan/v2)

### Contract-tested offline

Default CI and reviewer flows exercise the Scanning client, remote-state capture,
plan build, dry-run, and authorized apply against a deterministic local HTTP
contract server. This does **not** contact a live Microsoft Purview account and
does **not** claim live-tenant validation.

### Not claimed / not implemented

- Data Source kinds beyond AzureStorage
- Scan / SRS / Classification Rule kinds beyond the supported AzureStorage /
  Custom / AzureStorageMsi slice
- Unified Catalog (v1.2)
- automatic deletes
- production-scale operational hardening
- validation against a live Microsoft Purview environment

Limitation: remote Scans that expose explicit unsupported configurable fields
are blocked from safe comparison (`remote.unsupported_configurable_field`).

## Safety model (apply)

`execute_governance_plan(plan, client, *, mode=ExecutionMode.DRY_RUN)` is the
supported mutation boundary. CLI flags are not the security boundary.

Preflight order (fail-closed; zero PUT until complete):

1. revalidate plan document
2. validate exact `ExecutionMode`
3. `executionEligibility` + create/replace-only operations
4. bind logical target (`client.target_endpoint`) vs plan target
5. materialize all mutation payloads from the plan desired snapshot
6. fresh remote-state capture (`capture_remote_state` for plan/v1;
   `capture_remote_state_v2` for plan/v2)
7. compare `materialStateIdentity` to `plan.identities.remoteState`
8. dry-run (ready, zero PUT) or apply (sequential PUTs)

Write outcome classification:

- HTTP **200/201** → confirmed write (`writesPerformed`), independent of response body
- explicit **4xx** → `write-failed` / `apply.write_rejected`
- **5xx**, transport timeout/error, unexpected 2xx/3xx → `indeterminate` /
  `apply.write_outcome_unknown` (not claimed side-effect-free)
- token acquisition failure when starting a mutation (before `_send`) →
  `write-failed` / `apply.write_auth_failed` (deterministic; may follow a
  successful write prefix)

No automatic retry. No auto-replan. Residual TOCTOU between final GET and first
PUT is documented; v1 does not use ETags/CAS.

`writesAttempted` means the apply service initiated the PUT primitive after
preflight — not proof the server received bytes.

## Execution result provenance

`purview-execution-result/v1` records:

- `plannedTargetContextIdentity` vs `executionTargetContextIdentity`
- `plannedRemoteStateIdentity` vs `observedRemoteStateIdentity`

Status values prove which preflight stage completed (for example `wrong-target`
requires mismatched target identities and null observed remote;
`applied`/`write-failed`/`indeterminate`/`dry-run-ready` require
observed == planned remote identity).

## CLI

```text
purview-governance config validate CONFIG [--json]
purview-governance remote-state capture CONFIG --output remote.json [--force]
purview-governance plan create CONFIG --output plan.json [--force]
purview-governance plan inspect PLAN [--json]
purview-governance apply PLAN                 # dry-run (default)
purview-governance apply PLAN --apply [--result result.json] [--force] [--json]
purview-governance result inspect RESULT [--json]
```

Apply builds the Scanning client from the **plan** target endpoint (no external
config required for desired payload). `--force` never allows overwriting an input
artifact (plan/config). Output destination is preflight-checked before network.

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | success / dry-run-ready / applied |
| 2 | argparse usage |
| 3 | input/contract/path validation |
| 4 | blocked / wrong-target / stale |
| 5 | failed-before-write (auth/read/preflight) |
| 6 | write-failed / indeterminate / unexpected APPLY internal failure |
| 7 | local artifact persistence failure after execution |

An unexpected internal failure during `--apply` (exit 6) must not be treated as
pre-write success/failure certainty: capture fresh remote state and re-plan
before retrying. Dry-run never issues PUTs, so unexpected dry-run failures use
exit 5.

### Offline reviewer workflow (contract-tested)

```powershell
pip install -e ".[dev]"
pytest tests/cli/test_offline_v1_workflow.py -v
```

This exercises config → remote capture → plan → inspect → dry-run → apply against
the loopback contract server via a package-private CLI dependency seam. It does
not require Azure credentials and does not expose public `--base-url` / `--insecure`
flags.

## Quick start (clean checkout)

Requires Python 3.12+.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

ruff check .
ruff format --check .
pytest -m "not api_contract"
pytest -m api_contract
python -m build
```

Fictional sample config: `examples/fictional-governance-config.yaml`.

```powershell
purview-governance config validate examples/fictional-governance-config.yaml
```

## Repository structure

```text
src/purview_governance/
  auth/ config/ desired/ diff/ plan/ remote_state/ scanning/ apply/
  cli.py
examples/
tests/   # unit, api_contract, cli offline workflow
.github/workflows/ci.yml
CHANGELOG.md
```

## Current roadmap

- v1.0 — Purview Automation Foundation (**stable / released** as package `1.0.0`)
- v1.1 — Scanning and Classification as Code (next)
- v1.2 — Unified Catalog Governance
- v1.3 — Governance Drift and Operations
- v2.0 — Enterprise Automation and Extensibility

## License

MIT
