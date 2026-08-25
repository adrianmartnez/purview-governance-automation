# Unified Catalog offline reviewer workflow (contract v3)

This guide mirrors the offline CLI E2E in
`tests/cli/test_offline_v3_workflow.py`. It exercises Public Preview Unified
Catalog automation against a deterministic loopback contract server via the
package-private CLI dependency seam. It does **not** contact a live Microsoft
Purview tenant and is **not** live-tenant validation.

Enumeration is **permission-scoped**: empty lists mean zero visible items for
the credentials in use, not a complete catalog inventory.

## Prerequisites

```powershell
pip install -e ".[dev]"
```

Run the automated offline path:

```powershell
pytest tests/cli/test_offline_v3_workflow.py -v
pytest tests/cli/test_v3_cli_failures.py -v
```

## Seed scenario (happy path)

Desired config (contract v3):

- two Business Domains that already match remote → no BD writes
- one Data Product in remote `DRAFT` with a drifted managed field (description)
  → plan `replace` → one `PUT /datagovernance/catalog/dataProducts/{id}`
- two Glossary Terms absent remotely (parent then child) → two
  `POST /datagovernance/catalog/terms` (parent before child)

Expected mutating write log after `apply --apply`:

1. `PUT` data product
2. `POST` parent glossary term
3. `POST` child glossary term

Zero Business Domain `POST`, zero `DELETE`.

## Conceptual CLI sequence

Artifacts are **paired** for v3 (unlike Scanning v1/v2):

```text
config validate --json
remote-state capture --output remote-audit.json [--credential SELECTOR]
plan create --output plan.json --remote-state-output plan-remote.json [--credential SELECTOR]
plan inspect
apply --remote-state plan-remote.json --credential SELECTOR --result dry-result.json
apply --apply --remote-state plan-remote.json --credential SELECTOR --result result.json
result inspect
plan create --output replan.json --remote-state-output replan-remote.json   # converged empty ops
apply --apply --remote-state replan-remote.json --credential SELECTOR       # no-op writes
```

Notes:

- `--credential` is optional on capture/plan create (default credential path).
- `--credential` is **required** for ready apply (dry-run or `--apply`).
- Blocked plans apply without `--credential` (exit 4, zero token/HTTP).
- Dual plan + remote persistence is fail-closed and **not** atomic.
- `partial` apply status maps to exit code **6**.

## Credential selectors

| Selector | Typical material |
|----------|------------------|
| `azure-cli` | interactive Azure CLI login |
| `azure-developer-cli` | Azure Developer CLI |
| `client-secret` | `AZURE_CLIENT_ID` + `AZURE_CLIENT_SECRET` |
| `certificate` | `AZURE_CLIENT_ID` + `AZURE_CLIENT_CERTIFICATE_PATH` (+ optional password) |

Tenant always comes from config/plan `target.tenantId` — never `AZURE_TENANT_ID`.

## Failure matrix (see `test_v3_cli_failures.py`)

- v1/v2 + `--credential` → exit 3, `cli.credential_flag_unsupported`, no HTTP
- v3 `plan create` without `--remote-state-output` → exit 3
- v3 `apply` without `--remote-state` → exit 3
- ready apply without `--credential` → exit 3, `cli.credential_required`
- invalid local remote JSON → exit 3 before auth/HTTP
- blocked plan + valid local remote, no credential → exit 4, zero token/HTTP
- stdout/stderr must not echo client secrets or raw Bearer tokens

## Public example

Validate the fictional v3 sample (no network):

```powershell
purview-governance config validate examples/fictional-governance-config-v3.yaml
```
