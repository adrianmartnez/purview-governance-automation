# purview-governance-automation

Microsoft Purview governance automation in Python for deterministic Data Map scanning,
classification governance, catalog automation, drift detection, and safe API workflows.

Development package version: `0.1.0.dev0` (pre-v1.0; not a stable release).

## Status

Implemented after the package/CLI/CI foundation:

- installable Python package and packaging foundation (`src/` layout, wheel/sdist)
- minimal `purview-governance` CLI foundation (`--help`, `--version`)
- CI and offline test infrastructure (lint, unit tests, package validation,
  contract-lane harness readiness, CLI integration against an installed wheel)

Not implemented yet:

- versioned governance configuration contract (#8)
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

## Project direction

The project will focus on:

- Microsoft Purview Data Map automation
- registered data sources and scan configuration
- scan rule sets and classification rules
- deterministic desired-state comparison and planning
- safe, explicit API mutation boundaries
- governance drift detection
- Microsoft Purview Unified Catalog integration
- reproducible CLI and CI workflows
- contract-tested behavior without requiring a live Microsoft Purview account for
  the default test suite

## Design principles

1. Plan before apply.
2. Deterministic outputs and reproducible decisions.
3. Credentials never belong in committed configuration.
4. Read-only and dry-run workflows are the default.
5. Remote mutations must be explicit.
6. Preview Microsoft APIs remain isolated behind explicit compatibility boundaries.
7. Public documentation must distinguish implemented capabilities, contract-tested
   behavior, and validation against a live Microsoft Purview environment.

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

Package and CLI smoke should use the built wheel in a clean environment and run
from a temporary working directory outside the checkout so imports cannot come
from the source tree.

```bash
python -m venv .venv-wheel
# activate .venv-wheel, then:
pip install dist/purview_governance_automation-*.whl
# cd to a temp directory outside the repo, then:
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
