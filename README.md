# purview-governance-automation

Microsoft Purview governance automation in Python for deterministic Data Map scanning,
classification governance, catalog automation, drift detection, and safe API workflows.

Development package version: `0.1.0.dev0` (pre-v1.0; not a stable release).

## Status

Implemented:

- installable Python package and packaging foundation (`src/` layout, wheel/sdist)
- minimal `purview-governance` CLI foundation (`--help`, `--version`)
- CI and offline test infrastructure (lint, unit tests, package validation,
  offline API contract tests, CLI integration against an installed wheel)
- versioned governance configuration contract `purview-governance-config/v1` (#8):
  packaged JSON Schema, offline YAML/JSON parsing/validation/normalization,
  stable diagnostics, and a `config validate` application service (not yet exposed
  as a public CLI subcommand)
- Microsoft Entra authentication boundary (#9): `TokenCredential`-based provider,
  centralized Purview OAuth scope, sanitized auth errors, and a convenient
  `DefaultAzureCredential` factory (replaceable; offline/fake tests only by default)
- Purview Scanning Data Plane client foundation (#10), API version `2023-09-01`:
  Data Source list/get, internal create-or-replace primitive, bounded timeouts,
  sanitized errors, injectable HTTP transport for offline unit tests
- deterministic Purview API contract-test server (#11): real HTTP over loopback
  with fictional Data Source fixtures, request recording without raw
  Authorization values, and the `api-contract-tests` CI lane

Not implemented yet:

- remote state, diff, plan, and apply workflows (#12–#15)
- complete v1.0 CLI workflows and documentation (#16)
- stable `v1.0.0` release (#17)
- scans, scan rule sets, and classifications (v1.1)
- validation against a live Microsoft Purview environment

No production Purview capability is claimed. Behavior has not been validated against
a live Microsoft Purview environment.

The required CI check `api-contract-tests` exercises the Scanning client against a
deterministic local HTTP contract server. It does not contact a live Microsoft
Purview account.

## Governance configuration (v1)

Contract name: `purview-governance-config`. Contract version `1` is independent of
the package SemVer.

- Load YAML or JSON offline (no network calls, no remote writes).
- Duplicate object/mapping keys are rejected (`config.duplicate_key`); last-value-wins
  is never applied.
- YAML uses SafeLoader semantics via a strict `SafeLoader` subclass that only adds
  duplicate-key rejection.
- Unknown fields fail closed. Credential material field names are rejected with
  `config.secret_field_forbidden`.
- `resources` must be an empty array in v1 (no resource kinds are supported yet).
- Sample (fictional values only): `examples/fictional-governance-config.yaml`.

Application helpers:

```python
from purview_governance.config import validate_config_file

config = validate_config_file("examples/fictional-governance-config.yaml")
```

## Microsoft Entra authentication

The integration boundary accepts any `azure.core.credentials.TokenCredential` and
centralizes the Purview scope `https://purview.azure.net/.default`.

`create_default_azure_credential_provider()` builds a provider with
`DefaultAzureCredential` as a convenient supported factory. Callers may inject a
more specific credential instead. This has not been validated against a live
Microsoft Purview environment.

For non-interactive automation, Azure Identity environment conventions apply when
using the default factory, for example:

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_CLIENT_SECRET`

(or managed identity / other credential chain members supported by Azure Identity).
Do not put secrets in governance configuration files.

This project does not enable detailed Azure Identity credential logging. Consumers
should not enable sensitive credential logging in environments where logs are not
adequately protected.

## Scanning Data Plane client foundation

`PurviewScanningClient` targets the Microsoft Purview Scanning Data Plane API
version `2023-09-01` for the v1 Data Source read path (list/get) and exposes an
internal create-or-replace primitive for later explicit apply. It uses HTTPS
endpoints normalized by the governance config contract, obtains `Authorization`
only in memory via `PurviewAuthorizationProvider`, applies bounded connect/read
timeouts, does not follow redirects, and does not perform automatic retries or
automatic writes.

Default unit tests use fake credentials and injected/mocked HTTP transports.
Contract tests use a deterministic loopback HTTP server with fictional fixtures.
Neither lane contacts a live Microsoft Purview account.

## Development

Requires Python 3.12+.

```bash
python -m venv .venv
# PowerShell
.\.venv\Scripts\Activate.ps1
# POSIX
source .venv/bin/activate
pip install -e ".[dev]"

ruff check .
ruff format --check .
pytest -m "not api_contract"
pytest -m api_contract

python -m build
```

Package and CLI smoke should use the built wheel in a clean environment under a
temporary directory outside the checkout (for example `$TEMP` / `$RUNNER_TEMP`) so
imports cannot come from the source tree.

```bash
# create a temp venv outside the repo, install the wheel, then from a temp cwd:
purview-governance --version
purview-governance --help
python -m purview_governance --version
python -m purview_governance --help
```

## Current roadmap

- v1.0 — Purview Automation Foundation
- v1.1 — Scanning and Classification as Code
- v1.2 — Unified Catalog Governance
- v1.3 — Governance Drift and Operations
- v2.0 — Enterprise Automation and Extensibility

Detailed milestones and issues are tracked in GitHub.

## License

MIT
