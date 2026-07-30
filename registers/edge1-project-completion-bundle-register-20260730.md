# Edge1 Project Completion Bundle Register

Date: 2026-07-30  
Classification: internal operations; no credentials or raw alert data  
System: Edge1 / WW.CX Security Observability  
Repository state: merged through PR #134 as `00904a2d26b4b3b14e18144c9bccd29b3a9f10b1`; not executed on Edge1

## Trigger

The security-observability repository phases were complete, but host-dependent work remained:

- live activation and acceptance of the Network Defense 600-second network-source freshness threshold;
- read-only Apache, route, header, CORS, directory-listing, and public-filesystem inventory;
- host sizing and SQLite evidence before protected Suricata-retention runtime implementation;
- protected evidence capture.

No authenticated Edge1 shell was available in the authoring runtime.

## Registered assets

| Asset | Purpose | Mutation boundary |
| --- | --- | --- |
| `deploy/activate-network-defense-freshness.sh` | Backup, install one service unit, execute one-shot exporter, verify endpoints, and roll back on failure | Installs only `wwcx-network-defense.service`; writes existing Network Defense status through the service |
| `tools/security/edge1-project-completion-preflight.sh` | Protected read-only host, Apache, route, header, filesystem, retention-size, and SQLite evidence | Writes only protected evidence and staged minimized output |
| `tests/test_edge1_project_completion_bundle.py` | Shell syntax and static safety validation | None |
| `docs/security/edge1-project-completion-runbook-20260730.md` | Exact operator sequence and claim boundary | None |

## Freshness activation controls

The activation requires authenticated root execution, repository `main`, a clean worktree, the merged freshness commit, protected evidence mode `0700`, backups, and automatic rollback.

It verifies:

- targeted tests and Network Defense repository validation;
- exact installed-unit equivalence;
- service result and exit status;
- network stale threshold `600`;
- unchanged verified-enforcement count;
- DNS policy `not_staged`;
- DNS enforcement false and unverified;
- `traffic_controls_changed:false`;
- unchanged timer enabled/active state;
- local and real-domain JSON acceptance;
- SHA-256 evidence.

It does not enable, disable, start, stop, or reschedule the timer.

## Completion preflight controls

The preflight captures host, principal, repository, systemd, capacity, Apache syntax/vhost/module/redacted directives, public-root metadata/hashes, anonymous local/public route and security-header evidence, SQLite capabilities, sanitized alert-size distribution, staged minimized summary, and a SHA-256 evidence manifest.

It performs no service control, Git update, Apache reload, authentication change, `/var/www` write, public route change, or protected-control mutation.

## Repository validation and merge

Exact bundle head: `6060348f4fcfcc955f93c4739a167321fe488013`

| Validation | Result |
| --- | --- |
| Shell syntax and static safety tests | Passed |
| `Validate repository` run 626 | Success |
| `Edge1 Operator Validation` run 458 | Success |
| Zero commits behind `main` | Confirmed |
| Mergeability | Confirmed |
| Unresolved review threads | None |
| PR #134 | Merged as `00904a2d26b4b3b14e18144c9bccd29b3a9f10b1` |

Changed scope was limited to two scripts, one validator, `tests/__init__.py`, the runbook, this register, and `.agent` continuity records.

## Execution status

| Item | State |
| --- | --- |
| Repository implementation | Complete and merged |
| Exact-head CI | Passed |
| PR scope/merge review | Passed |
| Edge1 authenticated preflight | Not executed; no authenticated path in this runtime |
| Edge1 freshness activation | Not executed; no authenticated path in this runtime |
| Public cutover | Not authorized or performed |
| Protected-retention runtime | Not implemented or deployed |

## Remaining authority boundaries

Exact separate authorization remains required before:

- publishing the minimized summary under `/var/www`;
- changing Apache aliases, headers, authentication, proxying, or routes;
- removing currently published detailed artifacts;
- activating an authenticated browser/session boundary;
- certificate, listener, DNS, firewall, or production-traffic changes;
- deleting retained status, report, incident, or evidence data.

## Safety statement

The repository bundle changed no live host. It contains no credentials or raw alert records. It does not authorize public disclosure, authentication changes, traffic-control changes, or production cutover.
