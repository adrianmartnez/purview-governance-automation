# purview-governance-automation

[![CI](https://github.com/fgnfmackk/purview-governance-automation/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/fgnfmackk/purview-governance-automation/actions/workflows/ci.yml)

Microsoft Purview governance automation in Python: declare desired Scanning
configuration as code, compare it to remote state, produce a deterministic plan,
and apply create-or-replace mutations only with an explicit opt-in.

Stable package version: `1.0.0` (v1.0 released / stable).

`main` develops toward stable **v1.1** as package `1.1.0.dev0` (Scans, Custom
Scan Rule Sets, and Custom Classification Rules: config/remote/diff/plan/apply
v2). Controlled multi-resource apply accepts plan/v2 with dry-run default;
plan/v1 apply and execution-result/v1 remain frozen. No automatic deletes.
Explicit unsupported Scan configurables block safe comparison. No live-tenant
validation claim.

Package SemVer is independent of machine-contract versions
(`purview-governance-config/v1` + `/v2`, `purview-remote-state/v1` + `/v2`,
`purview-governance-plan/v1` + `/v2`, `purview-execution-result/v1` + `/v2`).
Contract v1 remains frozen for package `1.0.0` compatibility; contract v2 is the
multi-resource surface used by v1.1. See [CHANGELOG.md](CHANGELOG.md).

## Status

### Implemented

- installable Python package (`src/` layout, wheel/sdist) and five CI gates:
  `lint`, `unit-tests`, `package-validation`, `api-contract-tests`, `cli-integration`
- versioned config `purview-governance-config/v1` (AzureStorage Data Sources) and
  `/v2` (AzureStorage Data Sources, Custom Classification Rules, Custom
  AzureStorage Scan Rule Sets, AzureStorageMsi Scans)
- Microsoft Entra auth boundary (`DefaultAzureCredential`, scope
  `https://purview.azure.net/.default`)
- Scanning Data Plane client pinned to API version `2023-09-01` (list/get +
  package-private create-or-replace receipt)
- deterministic loopback contract-test server
- read-only remote-state `purview-remote-state/v1` and `/v2`
- desired-vs-remote diff (create/replace/no-op/remote-only/blocked; no delete)
- versioned plan `purview-governance-plan/v1` and `/v2`
- safe explicit apply (`execute_governance_plan`) with dry-run default
  (plan/v1 → execution-result/v1; plan/v2 → execution-result/v2)
- execution result `purview-execution-result/v1` (frozen) and `/v2`
- CLI workflows for config/remote-state/plan/apply/result (v1 and v2 by
  `apiVersion`; apply accepts plan/v2)

### Contract-tested offline

Default CI and reviewer flows exercise the Scanning client, remote-state capture,
plan build, dry-run, and authorized apply against a deterministic local HTTP
contract server. This does **not** contact a live Microsoft Purview account and
does **not** claim live-tenant validation. Offline contract tests are not a
substitute for production validation against Microsoft Purview.

### Not claimed / not implemented

- Data Source kinds beyond AzureStorage
- Scan / SRS / Classification Rule kinds beyond the supported AzureStorage /
  Custom / AzureStorageMsi slice
- Unified Catalog (v1.2)
- automatic deletes
- automatic retries
- rollback
- production-scale operational hardening
- validation against a live Microsoft Purview environment

Limitation: remote Scans that expose explicit unsupported configurable fields
are blocked from safe comparison (`remote.unsupported_configurable_field`).

## Safety model (apply)

`execute_governance_plan(plan, client, *, mode=ExecutionMode.DRY_RUN)` is the
supported mutation boundary. CLI flags are not the security boundary.

Dry-run is the default. Mutation requires explicit opt-in (`ExecutionMode.APPLY`
/ CLI `--apply`). Fresh remote-state capture runs before writes for the
staleness gate. No automatic deletes. No automatic retries. No rollback.
Unsupported material fails closed.

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

`purview-execution-result/v1` and `/v2` record:

- `plannedTargetContextIdentity` vs `executionTargetContextIdentity`
- `plannedRemoteStateIdentity` vs `observedRemoteStateIdentity`

Status values prove which preflight stage completed (for example `wrong-target`
requires mismatched target identities and null observed remote;
`applied`/`write-failed`/`indeterminate`/`dry-run-ready` require
observed == planned remote identity). Result/v2 carries multi-resource operation
rows (including composite Scan identity via `dataSourceName`).

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

### CLI capture semantics (important)

These commands are **not** a chained artifact pipeline:

- `remote-state capture` performs a read-only capture and writes an independent
  snapshot useful for inspection/audit. That file is **not** an input to
  `plan create`.
- `plan create CONFIG` performs a **fresh** remote capture, runs the
  desired-vs-remote comparison internally, and writes a deterministic plan.
  There is no CLI `diff` command; comparison evidence is embedded in the plan
  and visible via `plan inspect` (`summary` / `operations` / `blockedFindings`).
- `apply PLAN` performs another **fresh** remote capture for the staleness gate
  before any write (dry-run or `--apply`).

Apply builds the Scanning client from the **plan** target endpoint (no external
config required for desired payload). `--force` never allows overwriting an input
artifact (plan/config). Output destination is preflight-checked before network.

### Reviewer flow (conceptual)

Independent evidence:

```text
config validate
remote-state capture   →  remote.json (audit snapshot only)
```

Plan and controlled apply (each step that needs remote state re-captures):

```text
config
→ plan create          (fresh capture + desired-vs-remote comparison + plan)
→ plan inspect
→ apply                (dry-run; fresh staleness capture; zero PUT)
→ apply --apply        (fresh staleness capture; controlled writes)
→ result inspect
→ plan create          (fresh capture after apply)
→ no-op plan           (operations empty when converged)
→ apply --apply        (no-op; writesAttempted == 0)
```

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
pytest tests/cli/test_offline_v2_workflow.py -v
```

Both exercises run against the loopback contract server via a package-private CLI
dependency seam. They do not require Azure credentials and do not expose public
`--base-url` / `--insecure` flags.

- **v1** — Data Source config/plan/apply/result path (frozen 1.0.0 surface).
- **v2** — multi-resource path using `examples/fictional-governance-config-v2.yaml`
  (validate → independent remote capture → plan create/inspect → dry-run →
  explicit apply → result inspect → empty re-plan → no-op apply). Demonstrates
  convergence after successful apply.

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

Fictional sample configs:

- `examples/fictional-governance-config.yaml` (config/v1)
- `examples/fictional-governance-config-v2.yaml` (config/v2 multi-resource)

```powershell
purview-governance config validate examples/fictional-governance-config.yaml
purview-governance config validate examples/fictional-governance-config-v2.yaml
```

## Repository structure

```text
src/purview_governance/
  auth/ config/ desired/ diff/ plan/ remote_state/ scanning/ apply/
  cli.py
examples/
tests/   # unit, api_contract, cli offline workflows (v1 + v2)
.github/workflows/ci.yml
CHANGELOG.md
```

## Current roadmap

- v1.0 — Purview Automation Foundation (**stable / released** as package `1.0.0`)
- v1.1 — Scanning and Classification as Code (**in development** on `main` as
  package `1.1.0.dev0`; stable `1.1.0` is a separate release issue)
- v1.2 — Unified Catalog Governance
- v1.3 — Governance Drift and Operations
- v2.0 — Enterprise Automation and Extensibility

## License

MIT
