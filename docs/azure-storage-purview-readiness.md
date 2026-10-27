# Azure Storage security and Microsoft Purview scan-readiness (offline)

This guide is an **offline, fictional** walkthrough of Azure Storage security
readiness for Microsoft Purview scanning. It incorporates topics from Microsoft
Applied Skills **APL-1003** (*Secure storage for Azure Files and Azure Blob
Storage*) as **storage-security learning context only**. APL-1003 is **not** a
Microsoft Purview integration certification.

It does **not** contact a live Microsoft Purview tenant or a live Azure
subscription. Passing checks against fictional evidence does **not** mean a real
Azure resource is secure. Offline contract tests prove repository contract
behavior only — they are **not** Azure security validation and **not**
verification of a real Purview scan.

Microsoft Purview does **not** administer the full Azure Storage security
configuration surface (networking, encryption keys, soft delete, SMB settings,
and similar controls remain Azure Storage / identity / networking
responsibilities).

## Three independent responsibilities

| Layer | Responsibility | What this repo automates (v1.2.0) |
|-------|----------------|----------------------------------|
| **Azure Storage** | Account and share security, availability, encryption, network isolation, retention, and recovery | Nothing — out of scope for the automation engine |
| **Microsoft Purview Data Map** | Register sources, choose authentication and integration runtime, define and run scans | `AzureStorage` Data Sources, `AzureStorageMsi` Scans, Custom AzureStorage Scan Rule Sets, Custom Classification Rules (config/plan/apply **v2**) |
| **Microsoft Purview Unified Catalog** | Represent and govern scanned metadata (domains, products, terms, and related catalog objects) | Separate **v3** surface — not required for this Storage readiness walkthrough |

**Boundary:** Purview scan-readiness prerequisites (roles, credentials, IR, network
path to the source) are distinct from Azure Storage hardening. Meeting one does
not prove the other.

## References (Microsoft Learn)

As documented on Microsoft Learn at the time of writing:

- [APL-1003 study guide](https://learn.microsoft.com/en-us/credentials/applied-skills/resources/study-guides/apl-1003)
- [Discover and govern Azure Blob Storage](https://learn.microsoft.com/en-us/purview/register-scan-azure-blob-storage-source)
- [Connect to and manage Azure Files in Microsoft Purview](https://learn.microsoft.com/en-us/purview/register-scan-azure-files-storage-source)
- [Security recommendations for Blob storage](https://learn.microsoft.com/en-us/azure/storage/common/storage-security-guide)
- [Enforce a minimum required TLS version for Azure Storage](https://learn.microsoft.com/en-us/azure/storage/common/transport-layer-security-configure-minimum-version)
- [Networking considerations for Azure Files](https://learn.microsoft.com/en-us/azure/storage/files/storage-files-networking-overview)

## Scenario A — Fictional Azure Blob Storage

### Profile (fictional)

| Field | Declared fictional value |
|-------|--------------------------|
| Storage account | `stgcontosoanalytics` (not a real subscription resource) |
| Purview account endpoint (config example) | `https://contoso-fictional.purview.azure.com` |
| Blob endpoints in repo sample | `https://a.blob.core.windows.net/`, `https://b.blob.core.windows.net/` |
| Intended scan auth (Purview) | Managed identity (`AzureStorageMsi` in supported automation) |
| Anonymous / public blob access (ARM) | `allowBlobPublicAccess = false` |
| Public network access (declared) | Enabled for **selected networks** (not fully disabled) |
| Firewall default action (declared) | **Deny** |
| Private endpoints (declared) | **None** |
| Trusted Microsoft services exception (declared) | **Enabled** for the chosen Purview scanning path |
| Integration runtime (declared intent) | **Azure IR** |
| Managed identity data-plane role (declared intent) | **Storage Blob Data Reader** on the fictional account scope |
| Encryption at rest (declared) | Microsoft-managed keys (MMK); CMK **not** declared |
| Data protection (declared) | Soft delete for blobs and containers enabled; versioning enabled |
| TLS / transfer (declared) | Secure transfer required; minimum TLS **1.2** |

These values exist only as **fictional-config** evidence for the matrix below.
They are not observations from Azure Resource Manager or the Azure portal.

**Network public access is not anonymous blob access.** Selected-networks /
firewall rules control *who can reach the account endpoint*;
`allowBlobPublicAccess` controls whether anonymous (unauthenticated) public
read of blobs/containers is permitted. Matrix `PASS` rows for Scenario A
evaluate **declared fictional coherence** only. Live reachability, effective
RBAC, DNS, and real Purview scans remain unverified — see `LIVE-SCAN-01`.

### Security and availability topics (Azure Storage)

Aligned with APL-1003 / Azure Storage guidance, evaluate on the Azure side
(outside this repository’s engine):

- Secure transfer required (HTTPS).
- Minimum TLS version — Microsoft recommends **TLS 1.2** as the minimum for
  storage accounts where the account TLS setting applies.
- Anonymous / public blob access disabled unless a deliberate public scenario
  requires it.
- Storage firewall / selected networks, service endpoints, and private endpoints
  with correct private DNS.
- Encryption at rest (MMK by default; CMK via Key Vault when required).
- Soft delete, versioning, immutability / retention, and redundancy appropriate
  to the recovery objective.
- Least-privilege identity for data plane access (prefer Microsoft Entra ID over
  Shared Key where possible for Blob).

### Purview Data Map prerequisites (Blob)

As documented for Azure Blob Storage in Microsoft Purview:

| Networking constraint | Integration runtime | Documented credential types |
|-----------------------|---------------------|-----------------------------|
| No private endpoints or firewalls | Azure IR | Managed identity (recommended), service principal, or account key |
| Firewall enabled, no private endpoints | Azure IR | Managed identity |
| Private endpoints enabled | Self-hosted IR | Service principal or account key |

Typical managed-identity data-plane role for scanning Blob: **Storage Blob Data
Reader** on the storage account (or appropriate scope). When a firewall is
enabled, Purview documentation describes allowing trusted Microsoft services for
the scanning path where that exception applies.

Portal registration still requires the documented Purview data-source
administrator / reader roles for the account.

### Relationship to this repository

The public sample
[`examples/fictional-governance-config-v2.yaml`](../examples/fictional-governance-config-v2.yaml)
declares:

- Two Data Sources with `kind: AzureStorage` and blob HTTPS endpoints.
- One Custom Classification Rule and one Custom AzureStorage Scan Rule Set.
- Two Scans with `kind: AzureStorageMsi` (composite identity: same scan name under
  different data sources).

**Automated here:** desired-state config validation, offline plan/apply against a
loopback Scanning contract server for that `AzureStorage` / `AzureStorageMsi`
slice.

**Not automated here:** Azure Storage networking, TLS/minimum version on the
account, encryption key management, soft delete, redundancy, Key Vault, or live
Purview registration against a tenant.

## Scenario B — Fictional Azure Files (documentary only)

This scenario is **independent** of Scenario A and of the repository’s Scanning
automation. This repository does **not** implement an Azure Files adapter and
must not be read as claiming Azure Files plan/apply support.

### Chosen concrete scenario

| Field | Declared fictional value |
|-------|--------------------------|
| Resource provider | Classic Azure Files — **`Microsoft.Storage`** storage account + file share |
| Primary client protocol | **SMB 3.1.1** with channel encryption |
| Same-account data plane also considered | **FileREST** (HTTPS) for portal/tooling paths |
| Share name (fictional) | `finance-share` |
| Purview connector auth (documented) | **Account Key** stored as a Key Vault secret and referenced as a Purview credential |
| Integration runtime (declared intent) | Azure IR if the share is reachable per Purview networking guidance; otherwise managed VNet or self-hosted IR as required |
| Soft delete / recovery (declared) | Share soft delete enabled (fictional declaration) |
| Redundancy (declared) | ZRS for the fictional account |

**Out of scenario (mentioned only to bound scope):**

- **`Microsoft.FileShares`**: NFS-only provider per Azure Files networking
  documentation. This walkthrough does **not** assume Microsoft Purview connector
  compatibility with that provider unless Microsoft Learn documents it for the
  Azure Files source.
- **NFS** on classic shares: encryption in transit uses a TLS tunnel (AzNFS /
  stunnel, TLS 1.2 or 1.3) in the compatible mount mode. Not the primary
  protocol of this fictional share.

### Encryption in transit by protocol

Do **not** treat “minimum TLS” as globally inapplicable to Azure Files. Controls
differ by protocol (see Azure Files networking overview):

| Protocol | In-transit protection | Notes for this scenario |
|----------|----------------------|-------------------------|
| **FileREST** | HTTPS; TLS 1.2 or TLS 1.3. New storage accounts require HTTPS by default. A **minimum TLS version** can be set on the storage account for FileREST clients. | Applies to FileREST on the classic account; evaluate `MinimumTlsVersion` for FileREST, not as a substitute for SMB channel encryption. |
| **SMB** | SMB 3.x **channel encryption** (AES-128-CCM with SMB 3.0; AES-128-GCM and AES-256-GCM with SMB 3.1.1). SMB 2.1 does **not** support channel encryption. | Primary check for this share: SMB 3.x encryption negotiated; not the same control as account `MinimumTlsVersion`. |
| **NFS** | Encryption in transit via a TLS tunnel (AzNFS mount helper / stunnel; TLS 1.2 or 1.3) in the compatible modality. | **NOT_APPLICABLE** to this SMB-primary fictional share unless NFS is explicitly in scope. |

### Network, DNS, and protection (Azure Files)

For classic `Microsoft.Storage` file shares, plan public vs private endpoints,
DNS (`*.file.core.windows.net` / private DNS for private endpoints), SMB port
445 considerations for on-premises clients, share-level soft delete / snapshots /
backup as recovery controls, and redundancy. These remain Azure Storage
responsibilities.

### Purview connector authentication (delimited)

Microsoft Learn documentation for registering and scanning **Azure Files** in
Microsoft Purview currently describes **Account Key** authentication (access key
copied into Azure Key Vault, then a Purview credential). That statement applies
to the **documented Purview Azure Files connector**, not to every authentication
mechanism Azure Files supports for clients (for example identity-based SMB
access / Kerberos / Microsoft Entra scenarios on the service itself).

Do not invent additional Purview credential types for Azure Files beyond what
Learn documents for that connector. Do not reuse the repository’s
`AzureStorageMsi` automation as evidence that Azure Files scanning is automated.

### Blob vs Azure Files (scan-readiness differences)

| Topic | Azure Blob (Scenario A) | Azure Files (Scenario B) |
|-------|-------------------------|---------------------------|
| Repo automation (v2) | `AzureStorage` + `AzureStorageMsi` supported | **Not supported** — documentary only |
| Purview connector auth (Learn) | Managed identity recommended; SP and account key also documented by network posture | **Account Key** for the documented connector |
| In-transit controls | HTTPS + account minimum TLS | FileREST TLS / SMB channel encryption / NFS TLS tunnel — protocol-specific |
| Resource providers | Blob on `Microsoft.Storage` | Classic `Microsoft.Storage` shares vs `Microsoft.FileShares` (NFS-only); this scenario uses classic only |
| Typical IR coupling | Azure IR / managed VNet / self-hosted per network constraints | Same IR families; choose based on reachability to the file share |

## Evidence matrix

**How to read results**

- `PASS` / `FAIL` — only against a **defined check** using **available
  `fictional-config` or `local-repo-validation` evidence**. They never certify a
  live Azure resource. A Microsoft Learn citation alone is **not** a `PASS`/`FAIL`
  outcome.
- `UNKNOWN` — insufficient evidence (including no live tenant).
- `NOT_APPLICABLE` — the check does not apply to the named protocol or resource;
  justification required.
- Evidence kind values:
  - `fictional-config` — declared in a fictional scenario above
  - `microsoft-learn` — requirement text cited from Microsoft Learn (**not** an
    evaluation outcome; do not assign `PASS`/`FAIL` to this kind alone)
  - `local-repo-validation` — `config validate` or offline pytest loopback
    assertions only
  - `unavailable-no-tenant` — cannot verify without a real Azure / Purview tenant

Rows with `local-repo-validation` demonstrate **repository contract behavior**.
They are **not** Azure Storage security validation and **not** proof that a
Microsoft Purview scan succeeded against a real account.

| Check ID | Resource | Requirement | Evidence | Evidence source | Evidence kind | Result | Justification | Limitations |
|----------|----------|-------------|----------|-----------------|---------------|--------|---------------|-------------|
| BLOB-TLS-01 | Fictional account `stgcontosoanalytics` (Blob / account TLS) | Secure transfer required; minimum TLS 1.2 | Scenario A declares both settings | This document, Scenario A | `fictional-config` | `PASS` | Declared fictional posture meets the defined check | Fiction only; not ARM/portal proof |
| BLOB-PUB-01 | Same fictional Blob account | Anonymous/public blob access disabled (`allowBlobPublicAccess = false`) | Scenario A declares `allowBlobPublicAccess = false` | This document, Scenario A | `fictional-config` | `PASS` | Check evaluates the ARM anonymous/public blob access declaration only | Fiction only; selected-networks / firewall rows are **not** evidence for this check — do not infer from network rules |
| BLOB-CMK-01 | Same fictional Blob account | Customer-managed keys configured | CMK not declared; only MMK declared | This document, Scenario A | `fictional-config` | `UNKNOWN` | Insufficient fictional evidence to claim CMK compliance | Do not infer CMK from MMK default |
| BLOB-NET-01 | Same fictional Blob account | Fictional connectivity declaration is complete for the chosen path: selected networks + default Deny + no private endpoints + trusted Microsoft services exception + Azure IR + MSI intent | Scenario A declares each of those connectivity fields | This document, Scenario A | `fictional-config` | `PASS` | Defined check = internal coherence of the fictional connectivity story only | Not proof of live network path, DNS resolution, or storage reachability — see `LIVE-SCAN-01` |
| BLOB-PVW-01 | Fictional Blob scan path (Scenario A) | Declared Purview auth/IR align with Learn for firewall enabled and no private endpoints (Azure IR + managed identity) | Scenario A declares Azure IR, MSI / `Storage Blob Data Reader` intent, no PE, trusted Microsoft services; Learn documents MSI for that networking case | This document, Scenario A (Learn cited under Requirement) | `fictional-config` | `PASS` | Defined check = documentary alignment of fictional declarations with Learn guidance | Not a live connection test, not effective RBAC proof, not a completed scan — see `LIVE-SCAN-01` |
| FILES-SMB-01 | Fictional share `finance-share` (SMB) | SMB 3.x channel encryption in use | Scenario B declares SMB 3.1.1 with channel encryption | This document, Scenario B | `fictional-config` | `PASS` | Declared SMB posture meets the SMB check | Fiction only; not a packet capture |
| FILES-REST-01 | Same classic account (FileREST) | HTTPS with minimum TLS 1.2 for FileREST | Scenario B uses classic account; FileREST TLS/min TLS called out as account-level FileREST control | This document + Learn Files networking | `fictional-config` | `UNKNOWN` | Scenario emphasizes SMB encryption; FileREST minimum TLS value was not explicitly declared as a numeric setting | Do not treat SMB encryption as proof of FileREST `MinimumTlsVersion` |
| FILES-NFS-01 | Fictional share `finance-share` (NFS TLS tunnel) | NFS encryption-in-transit via TLS tunnel where NFS is used | Share is SMB-primary; NFS not in scenario | This document, Scenario B | `fictional-config` | `NOT_APPLICABLE` | NFS TLS-tunnel check does not apply to this SMB-primary fictional share | Would apply only if NFS were in scope |
| FILES-PVW-01 | Fictional Azure Files Purview path (Scenario B) | Declared connector auth is Account Key via Key Vault (Learn connector) | Scenario B declares Account Key + Key Vault for the Purview Azure Files connector | This document, Scenario B (Learn cited under Requirement) | `fictional-config` | `PASS` | Fictional declaration matches the documented connector auth; not a claim about all Azure Files client auth | Fiction + Learn citation; connector-scoped only |
| FILES-AUTO-01 | This walkthrough / package scope | Must not claim Azure Files plan/apply automation | Scenario B states documentary-only; no Azure Files kind in the v2 sample | This document, Scenario B + `examples/fictional-governance-config-v2.yaml` kinds | `fictional-config` | `PASS` | Defined honesty check on the walkthrough and sample kinds | Not an Azure security control; not pytest output |
| REPO-CFG-01 | `examples/fictional-governance-config-v2.yaml` | Config validates as `purview-governance-config/v2` without network | `purview-governance config validate` succeeds locally | CLI local schema validation | `local-repo-validation` | `PASS` | Local schema validation only | Not Azure security; not a live Purview scan |
| REPO-OFF-01 | Offline v2 CLI workflow | Loopback plan/apply assertions hold without Azure credentials | `tests/cli/test_offline_v2_workflow.py` | Pytest + package-private DI seam | `local-repo-validation` | `PASS` | Contract loopback behavior only | Writes hit loopback server only; never a real tenant |
| LIVE-SCAN-01 | Real Azure Blob/Files path + Purview scan | Live storage reachability, effective MSI/RBAC, DNS/private-link behavior if used, and end-to-end Purview scan succeed in an authorized tenant | No tenant / ARM/portal observation available for this walkthrough | — | `unavailable-no-tenant` | `UNKNOWN` | Cannot verify connectivity, effective permissions, or scan outcome without an authorized non-production tenant | Covers the live gaps left explicit by `BLOB-NET-01` / `BLOB-PVW-01` PASS (fiction-only) rows; required for live readiness claims |
| LEARN-REF-01 | Microsoft Learn (Blob + Files scan articles) | Official connector/auth/network requirements remain the external source of truth | URLs listed in References | Microsoft Learn | `microsoft-learn` | `UNKNOWN` | Citation only — Learn text is not scored as fictional compliance | Re-read Learn before live work; docs may change |

## Offline reviewer workflow

Prerequisites: Python 3.12+, clean checkout.

```powershell
pip install -e ".[dev]"
```

### 1. Validate fictional Blob governance config (no authentication)

```powershell
purview-governance config validate examples/fictional-governance-config-v2.yaml
```

Expected: process exit success and the CLI prints `config valid` (use `--json` for
`status` / `apiVersion` fields). This step does not build a Purview client and
does not require Azure credentials. Map the outcome to matrix row `REPO-CFG-01`
(`local-repo-validation` only).

### 2. Run the existing offline v2 contract workflow

```powershell
python -m pytest tests/cli/test_offline_v2_workflow.py -v
```

This test starts a loopback Scanning contract server and injects a
package-private `_CliDependencies` scanning client factory. It does **not**
expose public `--base-url` or `--insecure` flags.

What the test actually asserts (evidence for `REPO-OFF-01`):

1. `config validate --json` → `status == valid`, `apiVersion` config/v2.
2. Independent `remote-state capture` → empty remote lists (audit snapshot; not
   plan input).
3. `plan create` → six `create` operations (two Data Sources, one Classification
   Rule, one Scan Rule Set, two Scans).
4. Dry-run `apply` → `dry-run-ready`, `writes_attempted == 0`, zero PUT recordings.
5. `apply --apply` → six PUTs on the expected loopback paths; result `applied`.
6. Re-plan → empty operations; no-op apply keeps total PUTs at six.

**Do not** document a public Scanning `plan create` or `remote-state capture`
invocation as offline: without the private dependency seam those commands use
the configured client toward the config endpoint (real network / credential
path).

### 3. Interpret evidence

| Observed locally | May support | Must not claim |
|------------------|-------------|----------------|
| Config validates | `REPO-CFG-01` | Live Purview acceptance of the YAML |
| Pytest loopback green | `REPO-OFF-01` | Azure Storage is hardened; a real scan ran |
| Fictional Scenario A/B tables | `fictional-config` rows | Real ARM/portal configuration |
| Microsoft Learn citations | `microsoft-learn` requirement text | That your subscription already complies |

### 4. Confirm no Microsoft Azure connectivity is required

The steps above use local schema validation and a loopback HTTP server only.
They require no Purview account, no storage account, and no Entra credentials.

## What this demonstrates / does not demonstrate

**Demonstrates**

- How to separate Azure Storage hardening, Purview Data Map scanning, and Unified
  Catalog concerns.
- Protocol-specific in-transit controls for Azure Files (FileREST vs SMB vs NFS).
- That the Purview Azure Files connector’s documented Account Key auth is not the
  same claim as “Azure Files only supports Account Key.”
- How this repository’s existing `AzureStorage` / `AzureStorageMsi` offline path
  can be exercised without a tenant.
- How an evidence matrix should stay fail-closed on missing data (`UNKNOWN`).

**Does not demonstrate**

- Live-tenant Purview scanning or Azure policy compliance.
- Automatic collection or remediation of Azure Storage settings.
- Azure Files automation in this package.
- Unblocking of governance milestones v1.3 / v2.0 (issues #4 / #5).
- That APL-1003 certifies Purview integration skill.
