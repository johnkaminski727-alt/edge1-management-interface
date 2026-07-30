# Edge1 Security-Boundary Live Inventory Register

Date: 2026-07-30  
Classification: internal security and deployment-evidence control  
Repository baseline: `d236219067c78c584b06c11a5612c5ed28ef72fb`  
State: repository implementation; not executed on Edge1

## Objective

Provide the exact authenticated read-only host evidence required before protected retention installation, public-summary staging, restricted release construction, authenticated-route implementation, or anonymous detailed-route withdrawal.

## Authorization record

`config/security/edge1-security-completion-authorization-20260730.json` records the user's explicit authorization for the four named security-completion programs and the immutable guardrails. It contains no credential or secret material.

## Assets

| Asset | Function | Mutation boundary |
| --- | --- | --- |
| `tools/security/edge1-security-boundary-live-inventory.sh` | Root-run host inventory and evidence orchestration | Writes only beneath the protected evidence directory |
| `tools/security/reconcile-edge1-live-inventory.py` | Reconcile supplied JSON inventory against merged manifest and access policy | Reads supplied files; writes only optional result output |
| `tools/security/redact-edge1-boundary-text.py` | Stream redaction for unit, Apache, and HTTP evidence | Pure stdin/stdout transformation |
| `tests/test_edge1_security_boundary_live_inventory.py` | Authorization, non-mutation, redaction, and reconciliation tests | Temporary files only |
| `docs/security/edge1-security-boundary-live-inventory-runbook-20260730.md` | Operator execution and interpretation | Documentation only |

## Evidence contract

The host script creates:

```text
/var/lib/wwcx-deployment-evidence/edge1-security-boundary-live-inventory/<UTC timestamp>
```

The evidence includes exact source-tree SHA-256, mode, and byte records; anomaly reporting; route and header observations; Apache/module/provider-readiness metadata; service state; listeners; capacity; candidate-root metadata; reconciliation; and a SHA-256 evidence manifest.

## Privacy and credential controls

- no environment dump;
- no Git remote URLs;
- no SSH files or private keys;
- no shadow or password-file contents;
- no authorization or cookie request headers;
- no cookie values;
- no provider/client secret values;
- no audit-log contents;
- no copied Apache configuration contents;
- unit and HTTP evidence passes through the repository redactor;
- Apache records directive names only and hashes source files for equivalence.

## Non-mutation controls

The inventory contains no service start, stop, restart, reload, enable, disable, mask, or unmask operation. It contains no Apache enable/disable/reload operation, no file copy/move/removal, no ownership or mode change outside evidence-directory creation, no DNS/firewall/routing/IDS command, and no public or restricted route mutation.

## Reconciliation behavior

- exact known files map to `stage_candidate`;
- approved-prefix files map with `prefix_live_enumeration` provenance;
- unknown files remain `preserve_review`;
- missing exact files are reported;
- duplicate sources or targets fail closed;
- symlinks and non-regular files are reported separately;
- staging and cutover remain false under the committed disabled policies.

## Repository validation status

Pending exact-head validation and PR review for:

- Python unit and functional tests;
- shell syntax and static non-mutation checks;
- JSON validation;
- zero-behind and changed-file review;
- mergeability and review-thread review.

## Live status

No authenticated Edge1 execution occurred from the authoring runtime. No new evidence directory, filesystem inventory, route observation, service observation, or reconciliation result is claimed live.
