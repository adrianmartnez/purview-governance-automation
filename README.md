# purview-governance-automation

Microsoft Purview governance automation in Python for deterministic Data Map scanning,
classification governance, catalog automation, drift detection, and safe API workflows.

Development package version: `0.1.0.dev0` (pre-v1.0; not a stable release).

## Status

Implemented:

- installable Python package and packaging foundation (`src/` layout, wheel/sdist)
- minimal `purview-governance` CLI foundation (`--help`, `--version`)
- CI and offline test infrastructure (lint, unit tests, package validation,
  contract-lane harness readiness, CLI integration against an installed wheel)
- versioned governance configuration contract `purview-governance-config/v1` (#8):
  packaged JSON Schema, offline YAML/JSON parsing/validation/normalization,
  stable diagnostics, and a `config validate` application service (not yet exposed
  as a public CLI subcommand)

Not implemented yet:

- Microsoft Entra authentication (#9)
- Purview Scanning Data Plane client (#10)
- Purview-specific API contract-test server (#11)
- remote state, diff, plan, and apply workflows (#12–#15)
- complete v1.0 CLI workflows and documentation (#16)
- stable `v1.0.0` release (#17)

No production Purview capability is claimed. Behavior has not been validated against
a live Microsoft Purview environment.

The required CI check `api-contract-tests` currently validates only offline readiness
of the contract-test lane harness. Issue #11 will introduce the Purview-specific
mock/contract server.

## Governance configuration (v1)

Contract name: `purview-governance-config`. Contract version `1` is independent of
the package SemVer.

- Load YAML or JSON offline (no network calls, no remote writes).
- Duplicate object/mapping keys are rejected (`config.duplicate_key`); last-value-wins
  is never applied.
- YAML uses SafeLoader semantics via a strict `SafeLoader` subclass that only adds
  duplicate-key rejection and string-key enforcement.
- Unknown fields fail closed. Credential material field names are rejected with
  `config.secret_field_forbidden`.
- `resources` must be an empty array in v1 (no resource kinds are supported yet).
- Sample (fictional values only): `examples/fictional-governance-config.yaml`.

Application helpers:

```python
from purview_governance.config import validate_config_file

config = validate_config_file("examples/fictional-governance-config.yaml")
```

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
