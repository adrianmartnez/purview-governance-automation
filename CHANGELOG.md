# Changelog

All notable changes to this project are documented in this file.

The format is inspired by [Keep a Changelog](https://keepachangelog.com/),
and this project uses [Semantic Versioning](https://semver.org/) for the
**Python package**. Package SemVer is independent of machine-contract versions
(`purview-*-config/v1` + `/v2` + `/v3`, plan/result/remote-state `/v1` + `/v2`
+ `/v3`, execution-result `/v1` + `/v2` + `/v3`).
Contract `v1` does not mean package version `1.0.0`; a future package `1.x` may
keep contract `v1` while those artifacts remain compatible.

## [Unreleased]

## [1.2.0] - 2026-08-25

Stable package release for Unified Catalog Governance, with Microsoft Purview
Unified Catalog Public Preview isolated behind contract v3, deterministic
planning, bounded controlled apply, read-model governance evidence, and
reviewer-oriented CLI workflows.

### Added

- Isolated `unified_catalog` adapter (`PurviewUnifiedCatalogClient`) for
  Microsoft Purview Unified Catalog Public Preview API `2026-03-20-preview`,
  with fail-closed production endpoint policy
  (`https://api.purview-service.microsoft.com`), compatibility metadata, and
  offline loopback contract coverage (separate from Scanning).
- Contract **v3** surfaces: `purview-governance-config/v3`,
  `purview-remote-state/v3`, `purview-governance-plan/v3`, and
  `purview-execution-result/v3` (including `partial` contiguous-prefix
  invariants).
- **Business Domains** declarative modeling via v3: target binding with declared
  `target.tenantId` and `compute_target_context_identity_v3`, deterministic
  diff/plan (parentId root ownership, description v2-semantics, explicit
  `isRestricted`, deferred-configurable safety, hierarchy limits), and default
  remote capture Shape A.
- **Data Products** declarative modeling via v3: opt-in remote capture Shape B,
  domain dependency resolution, deterministic ordering, and controlled apply
  CREATE + safe DRAFT REPLACE (domain move fail-closed).
- **Glossary Terms** declarative modeling via v3: opt-in capture Shapes C/D,
  domain/parent dependency resolution, scoped hierarchy validation,
  parentId full ownership, acronyms three-state, and controlled apply CREATE +
  bounded safe REPLACE (parent-clear blocked fail-closed).
- **Data Assets / Data Columns** and governance relationship families A–C as
  **read-model-only** capture in remote-state/v3 (`readModelCoverage`; sparse
  positive-only); no desired-state/diff/plan/apply for those resource types.
- Controlled Unified Catalog **apply/v3** (`execute_governance_plan_v3`) with
  fail-closed full-plan preflight, dry-run default, paired planned remote-state,
  `TenantBoundAuthorizationProvider` at the APPLY seam, and
  `derive_capture_recipe()` for exact fresh-capture replay.
- Unified Catalog **CLI v3** workflows: `config validate`, `remote-state capture`,
  `plan create` (requires `--remote-state-output`), `plan inspect`,
  `apply` / `apply --apply` (requires `--remote-state`; `--credential` required
  for ready plans), and `result inspect`. Explicit `--credential` selectors;
  tenant always from config/plan (never `AZURE_TENANT_ID`). Offline reviewer
  guide: `docs/unified-catalog-reviewer-workflow.md`.
- Strict `load_remote_state_v3_text` / `load_remote_state_v3_file` for local
  planned remote-state/v3 artifacts.
- Example `examples/fictional-governance-config-v3.yaml` and offline UC contract /
  CLI E2E / failure-matrix tests; CI cli-integration smoke for fictional
  config/v3 validate and v3 help flags.
- `docs/contract-discovery/pr6-unified-catalog-apply.md` (apply/v3 safety gates).

### Changed

- Stable package version `1.2.0`.
- README release status and roadmap: v1.2 Unified Catalog Governance released as
  package `1.2.0` (package stable ≠ Microsoft Unified Catalog API GA).
- Package metadata description documents contracts `(v1+v2+v3)`.
- README capability matrix documents apply/v3 bounded support and
  blocked-capability semantics (`executionEligibility: blocked` is not a planner
  error; executor fails closed before any write).

### Fixed

- Apply/v3 early `failed-before-write` paths (invalid remote / remote identity
  mismatch) now set `executionTargetContextIdentity` to the planned target so
  result serialization matches fail-closed semantics.
- Data Product and Glossary Term description drift reasons now use
  `canonical_json_scalar` so plan self-validation accepts description replaces.
- README CI badge and package author metadata (`adrianmartnez`).

### Safety / limitations

- Unified Catalog API remains `2026-03-20-preview` **Public Preview**. Package
  `1.2.0` is a stable Python package release; that does **not** mean the
  Microsoft Unified Catalog API is GA.
- Capabilities are **offline contract-tested**. There is **no live-tenant
  validation claim**. Offline contract tests are not production Purview
  validation.
- Captures are **permission-scoped** (empty capture means zero visible items for
  the credentials used, not tenant-wide inventory).
- Dry-run is the default; mutation requires explicit `--apply` /
  `ExecutionMode.APPLY`. No automatic deletes, retries, rollback claim, or
  auto-replan.
- No Data Asset writes, Data Column ingest, relationship writes, or lineage
  writes.
- Business Domain **CREATE** unsupported/fail-closed; Business Domain **REPLACE**
  bounded only (blocked when deferred configurables would be clobbered).
- Data Product CREATE + safe DRAFT REPLACE; Glossary Term CREATE + bounded safe
  REPLACE; Glossary Term parent-clear blocked fail-closed.
- Declared `tenantId` is not live-verified against credentials.
- `executionEligibility: ready` means absence of known v3 blockers — not a
  Microsoft execution guarantee.
- DefaultAzureCredential / managed identity are unsupported for apply/v3
  (tenant-bound authorization required for ready plans).
- No automatic destructive reconciliation; no v4 contracts; no GA claim for UC.
- Unified Catalog client secret-sentinel coverage; bearer tokens are not
  persisted; Authorization is excluded from sanitized errors and contract
  recordings.

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
