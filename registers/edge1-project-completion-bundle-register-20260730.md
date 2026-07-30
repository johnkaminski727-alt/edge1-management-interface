# Edge1 Project Completion Bundle Register

Date: 2026-07-30  
Classification: internal operations; no credentials or raw alert data  
System: Edge1 / WW.CX Security Observability  
Repository state: live acceptance completed at `a06f035e7fcf933a03ec752c66ce0261c5a65ba7`

## Trigger

The security-observability repository phases were complete, but host-dependent work remained:

- live activation and acceptance of the Network Defense 600-second network-source freshness threshold;
- read-only Apache, route, header, CORS, directory-listing, and public-filesystem inventory;
- host sizing and SQLite evidence before any protected Suricata-retention runtime implementation;
- protected evidence capture.

The authoring runtime had no authenticated Edge1 shell. An authenticated operator later executed the prepared bundle through SSH on `edge1.ww.cx` as `wwadmin` using the documented `sudo` path.

## Registered assets

| Asset | Purpose | Mutation boundary |
| --- | --- | --- |
| `deploy/activate-network-defense-freshness.sh` | Backup, install one service unit, execute one-shot exporter, verify endpoints, and roll back on failure | Installs only `wwcx-network-defense.service`; writes existing Network Defense status through the service |
| `tools/security/edge1-project-completion-preflight.sh` | Protected read-only host, Apache, route, header, filesystem, retention-size, and SQLite evidence | Writes only protected evidence and staged minimized output |
| `tests/test_edge1_project_completion_bundle.py` | Shell syntax and static safety validation | None |
| `docs/security/edge1-project-completion-runbook-20260730.md` | Exact operator sequence and claim boundary | None |
| `registers/network-defense-freshness-live-acceptance-20260730.md` | Final operator evidence and acceptance record | None |

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

## Repository validation and correction

The operator bundle was merged through PR #134 as `00904a2d26b4b3b14e18144c9bccd29b3a9f10b1` after `Validate repository` run 626 and `Edge1 Operator Validation` run 458 passed.

The first live activation attempt exposed one stale test assumption: `tests/test_network_defense_runtime_wiring.py` expected the nftables exporter directly in `ExecStart`, while the accepted service intentionally used the freshness wrapper over the nftables-aware chain. Validation failed before `MUTATION_STARTED=1`, so no live service unit or status snapshot was replaced.

PR #136 corrected only the test contract:

| Validation | Result |
| --- | --- |
| Exact corrective head | `ea4ad48daf51aab5bbb2fbdf90b0a1767eefe353` |
| `Validate repository` run 636 | Success |
| `Edge1 Operator Validation` run 468 | Success |
| Zero commits behind `main` | Confirmed |
| Changed scope | One test file |
| Runtime/deployment files changed | None |
| PR #136 | Merged as `a06f035e7fcf933a03ec752c66ce0261c5a65ba7` |

## Live execution and acceptance

Read-only preflight passed at:

```text
/var/lib/wwcx-deployment-evidence/edge1-project-completion-preflight/20260730T193415Z
```

The preflight reported no Apache, authentication, route, listener, firewall, DNS, or public-file changes.

After the PR #136 correction was pulled, the bounded freshness activation passed at:

```text
/var/lib/wwcx-deployment-evidence/network-defense-freshness/20260730T195031Z
```

Accepted results:

| Control | Result |
| --- | --- |
| Network stale threshold | `600` seconds |
| Overall state | `limited` |
| Verified enforcement count | `1` before and after |
| DNS policy | `not_staged` |
| DNS enforcement | `false` |
| Traffic controls changed | `false` |
| Timer state | Unchanged |
| Live revision | `a06f035e7fcf933a03ec752c66ce0261c5a65ba7` |
| Activation | Successful; no rollback reported |

## Execution status

| Item | State |
| --- | --- |
| Repository implementation | Complete and merged |
| Exact-head CI | Passed |
| PR scope/merge review | Passed |
| Edge1 authenticated preflight | Complete |
| Edge1 freshness activation | Complete and accepted |
| Protected evidence | Captured at both exact paths above |
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

The completed live change was limited to the existing Network Defense observability service unit and one-shot status export. DNS stayed unstaged, enforcement count and timer state were unchanged, and traffic controls remained unchanged. No credentials or raw alert records are stored in this register.
