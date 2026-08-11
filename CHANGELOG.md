# Changelog

All notable changes to this project are documented in this file.

The format is inspired by [Keep a Changelog](https://keepachangelog.com/),
and this project uses [Semantic Versioning](https://semver.org/) for the
**Python package**. Package SemVer is independent of machine-contract versions
(`purview-*-config/v1` + `/v2`, plan/result/remote-state `/v1` + `/v2`).
Contract `v1` does not mean package version `1.0.0`; a future package `1.x` may
keep contract `v1` while those artifacts remain compatible.

## [Unreleased]

## [1.1.0] - 2026-08-11

First stable package release of Scanning and Classification as Code
(multi-resource config/remote-state/plan/apply v2).

### Added

- Config / remote-state / plan **v2** contracts for AzureStorage **Data Sources**,
  AzureStorageMsi **Scans**, **Custom AzureStorage Scan Rule Sets**, and
  **Custom Classification Rules** (read, compare, deterministic plan, and
  controlled apply).
- Multi-resource desired-vs-remote comparison (data sources, classification
  rules, scans, scan rule sets), including composite Scan identity and
  deterministic prerequisite ordering.
- Controlled multi-resource apply for `purview-governance-plan/v2` with dry-run
  default, explicit apply opt-in, fresh `purview-remote-state/v2` staleness gate,
  fail-closed writes, and `purview-execution-result/v2`.
- Loopback contract coverage for Scan, Scan Rule Set, and Classification Rule
  list/get/create-or-replace (including pagination fail-closed cases, contract-
  tested failure classes, and idempotent re-planning).
- Public multi-resource example `examples/fictional-governance-config-v2.yaml`
  and offline CLI reviewer workflow
  `tests/cli/test_offline_v2_workflow.py` (validate → independent remote
  capture → plan create/inspect → dry-run → explicit apply → result inspect →
  empty re-plan → no-op apply; no Azure credentials).

### Changed

- `purview-remote-state/v2` shape expands with required `classificationRules`
  and `uninterpretedClassificationRules`.
- `purview-governance-plan/v2` desired state requires `classificationRules`.
  Pre-#27 plan/v2 development documents without that key are rejected on load
  with `plan.development_shape_superseded` (no upconvert).

### Safety / limitations

- Apply dispatches by plan version: plan/v1 → execution-result/v1 (frozen);
  plan/v2 → execution-result/v2. Dry-run remains the default; mutation requires
  explicit opt-in. No automatic deletes, retries, rollback, or Tag Classification
  Version.
- Explicit unsupported Scan configurable fields block safe comparison
  (`remote.unsupported_configurable_field`).
- No claim of validation against a live Microsoft Purview tenant. Offline
  contract tests are not production or live Microsoft Purview validation.

## [1.0.0] - 2026-08-10

First stable package release of the Purview Automation Foundation vertical slice.

### Foundation

- Installable Python 3.12 package with `src/` layout, wheel, and sdist.
- Five protected CI gates: `lint`, `unit-tests`, `package-validation`,
  `api-contract-tests`, `cli-integration`.

### Config

- Versioned governance configuration `purview-governance-config/v1`.
- Deterministic validation and normalization.
- AzureStorage Data Source vertical slice.

### Auth

- Microsoft Entra boundary via `DefaultAzureCredential`.
- Purview scope `https://purview.azure.net/.default`.
- Credentials remain external to committed configuration.

### Scanning client

- Purview Scanning Data Plane client pinned to API version `2023-09-01`.
- Public Data Sources List/Get.
- Package-private create-or-replace primitive with receipt (not a public export).
- Bounded timeouts, no redirect following, sanitized errors.

### Remote state

- Canonical artifact `purview-remote-state/v1`.
- Material state identity for staleness checks.

### Diff

- Desired-vs-remote outcomes: create, replace, no-op, remote-only, blocked.
- No automatic delete path.

### Plan

- Versioned plan artifact `purview-governance-plan/v1`.
- Deterministic plan identity and inspectable operation list.
- Target, config, desired, and remote identities recorded in the plan.

### Apply

- Safe explicit apply via `execute_governance_plan`.
- Dry-run default; mutation requires explicit apply mode.
- Target validation and remote-state staleness checks before writes.
- Mutation payloads taken from the plan desired snapshot (payload authority).
- HTTP 200/201 treated as confirmed writes; explicit 4xx as write-failed;
  5xx/transport/unexpected outcomes as unknown/indeterminate.
- No automatic mutation retry; no auto-replan.
- Partial and indeterminate outcomes recorded truthfully for audit.

### Result

- Execution result artifact `purview-execution-result/v1`.
- `resultIdentity` plus planned vs execution target/remote provenance.
- `writesPerformed` / `writesAttempted` / `writesUnknown` counters.

### CLI

- `config validate`
- `remote-state capture`
- `plan create` / `plan inspect`
- `apply` (dry-run default) / `apply --apply`
- `result inspect`
- Exit codes `0`–`7` as documented in the README.

### Security and safety

- No secrets in committed configuration or machine artifacts.
- Sanitized error surfaces.
- No automatic delete reconciliation.
- No insecure public loopback override flags on the CLI.

### Testing

- Deterministic loopback Purview contract-test server.
- Offline reviewer workflow without a live Microsoft Purview account.
- Default CI does not require Azure credentials or a commercial tenant.

### Known limitations

- AzureStorage Data Source kind only.
- Scans, scan rule sets, and classifications are not implemented (v1.1 scope).
- Unified Catalog is not implemented (v1.2 scope).
- No automatic deletes.
- Residual TOCTOU between final remote read and first write (no ETag/CAS).
- No automatic mutation retry.
- No production-scale operational claim.
- No claim of validation against a live Microsoft Purview tenant.
