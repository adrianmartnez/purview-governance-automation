# purview-governance-automation

Microsoft Purview governance automation in Python for deterministic Data Map scanning, classification governance, catalog automation, drift detection, and safe API workflows.

## Status

Repository bootstrap and roadmap definition.

No production capability is claimed yet.

Implementation will be delivered incrementally through reviewed pull requests and versioned releases.

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
- contract-tested behavior without requiring a commercial tenant for the default test suite

## Design principles

1. Plan before apply.
2. Deterministic outputs and reproducible decisions.
3. Credentials never belong in committed configuration.
4. Read-only and dry-run workflows are the default.
5. Remote mutations must be explicit.
6. Preview Microsoft APIs remain isolated behind explicit compatibility boundaries.
7. Public documentation must distinguish implemented, contract-tested, and tenant-validated capabilities.

## Current roadmap

- v1.0 — Purview Automation Foundation
- v1.1 — Scanning and Classification as Code
- v1.2 — Unified Catalog Governance
- v1.3 — Governance Drift and Operations
- v2.0 — Enterprise Automation and Extensibility

Detailed milestones and issues are tracked in GitHub.

## License

MIT
