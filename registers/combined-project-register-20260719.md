# Combined Project Register

Date: 2026-07-19
Classification: internal, sanitized
System: Edge1 / Big Bird / WW.CX operational tooling
Status: current source of truth for archive preparation

## Purpose

This register supersedes `registers/combined-project-register-20260717.md` as the top-level recovery, handoff, and archive-preparation record. The earlier register remains a historical baseline.

Use this file first when restoring context, reviewing completed work, or deciding what remains.

## Current repository baseline

| Area | State | Evidence |
| --- | --- | --- |
| Repository | Active | `johnkaminski727-alt/edge1-management-interface` |
| Default branch | `main` | GitHub repository metadata |
| Archive-preparation branch | Active | `agent/archive-edge1-smoke-test-20260719` |
| Archive pull request | Open | PR #36, `Archive Edge1 authenticated smoke-test closeout` |
| Edge1 working path | Verified during smoke test | `/opt/edge1-management-interface` |
| Edge1 observed checkout | Historical snapshot | `d53354fc44c09c4b732a3f8227b8e6cfd6495dcd` on 2026-07-19 |

The observed Edge1 checkout is a timestamped host snapshot, not the current GitHub baseline. Reconcile with current `main` before future deployment work.

## Current archive records

| Record | Status | Path |
| --- | --- | --- |
| Top-level combined register | Current | `registers/combined-project-register-20260719.md` |
| Edge1 smoke-test register | Archive-ready | `registers/edge1-authenticated-smoke-test-register-20260719.md` |
| Edge1 sanitized closeout | Archive-ready | `docs/archive/edge1-authenticated-smoke-test-closeout-20260719.md` |
| Combined register index | Updated | `docs/autonomous-completion/04-combined-register-index.md` |
| Repository evidence map | Updated | `docs/records-governance/EVIDENCE_MAP.md` |
| Prior combined register | Superseded, retained | `registers/combined-project-register-20260717.md` |

## Edge1 authenticated smoke-test closeout

Evidence window: `2026-07-19T18:28:23Z` through `2026-07-19T18:28:26Z`.

| Check | Final state | Notes |
| --- | --- | --- |
| Host identity | Pass | `edge1.ww.cx`, principal `wwadmin` |
| Repository worktree | Pass at observation time | `main`, clean worktree |
| BigBird AI gateway | Pass | Active on loopback port 8787 |
| Numbering node | Pass | Active on loopback port 8093; health `ok` |
| Telephony console | Pass | Aggregate status endpoint returned HTTP 200 |
| Asterisk | Pass | Running under `safe_asterisk`; SIP and AMI listeners verified |
| MariaDB runtime | Pass | Active; observed accounts restricted to `localhost` |
| MariaDB public ingress | Pass | Blocked by default-drop nftables input policy |
| MariaDB VPN scope | Warning | Socket activation remains reachable from trusted `wg0` peers |
| Disk and inodes | Pass | Root disk 18% used; root inode use 5% |
| Memory | Warning | Elevated swap use; adequate available RAM |
| Fail2ban | Pass after correction | Enabled, active, seven jails verified |
| Logrotate | Pass after correction | Manual service run exited successfully |
| Failed systemd units | Pass after correction | Zero failed units |
| Messaging gateway | Warning | Inactive/absent; aggregate telephony status remains critical |
| Audit redaction | Failure | Temporary wrapper leaked a synthetic bearer value |

## Corrective actions completed outside Git

| Change | Result | Rollback note |
| --- | --- | --- |
| Created `/etc/fail2ban/jail.d/99-disable-incomplete-sshd.local` | Applied and validated | Remove only after confirming replacement jail behavior |
| Enabled and started `fail2ban.service` | Active with seven jails | Disable and stop only through reviewed rollback |
| Verified `iptables-nft` Fail2ban chains | Pass | No separate legacy firewall stack observed |
| Re-ran `logrotate.service` | `status=0/SUCCESS` | No rollback required |
| Checked failed systemd units | Zero failed units | Fresh verification required for current state |

The PBX-generated `/etc/fail2ban/jail.local` was not edited.

## Evidence and archive boundary

The host-local evidence directory was:

```text
/tmp/edge1-readonly-smoke-20260719T182823Z
```

It is ephemeral and must not be committed, uploaded, or imported into the private library because the temporary smoke-test redactor failed its synthetic bearer-value test.

Only the sanitized register and closeout document are approved for durable archival.

Excluded from repository and library archival:

- raw command transcripts and logs;
- credentials, tokens, keys, authorization headers, and private connection data;
- firewall and database dumps;
- customer, carrier, message, or call records;
- any claim that the timestamped Edge1 checkout is the current GitHub baseline.

## Private library state

Known historical private-library imports remain recorded in the superseded 2026-07-17 register. The new smoke-test closeout has **not** been imported into the Big Bird operations collection because an approved private-library write/import connector was not available in this session.

Import only these sanitized records when an approved connector is available:

- `registers/combined-project-register-20260719.md`
- `registers/edge1-authenticated-smoke-test-register-20260719.md`
- `docs/archive/edge1-authenticated-smoke-test-closeout-20260719.md`

Do not import the raw evidence directory or temporary smoke-test script.

## Restore anchors

| Item | Location |
| --- | --- |
| Working repository | `/opt/edge1-management-interface` |
| GitHub repository | `johnkaminski727-alt/edge1-management-interface` |
| Local bare remote | `/opt/git/edge1-management-interface.git` |
| Big Bird gateway | `/opt/bigbird-ai-gateway` |
| Private library database | `/var/lib/bigbird-ai-library/library.sqlite3` |
| Private library backups | `/var/backups/bigbird-ai-library` |
| Smoke-test register | `registers/edge1-authenticated-smoke-test-register-20260719.md` |
| Sanitized smoke-test closeout | `docs/archive/edge1-authenticated-smoke-test-closeout-20260719.md` |

## Remaining work

| Item | Priority | Boundary |
| --- | --- | --- |
| Merge PR #36 after repository checks | High | Routine documentation/repository work |
| Import sanitized closeout records into Big Bird operations library | High | Requires approved library-write connector |
| Implement persistent redaction utility and regression tests | High | Routine repository work |
| Reconcile Edge1 checkout with current GitHub `main` | Medium | Preserve local work; routine fetch/inspection |
| Trend swap use | Medium | Read-only inspection first |
| Decide whether MariaDB should remain VPN-reachable | Medium | Socket/firewall change requires production authorization |
| Complete read-only messaging-status activation | Separate track | Follow existing messaging activation gate |

## Restore reading order

1. `registers/combined-project-register-20260719.md`
2. `registers/edge1-authenticated-smoke-test-register-20260719.md`
3. `docs/archive/edge1-authenticated-smoke-test-closeout-20260719.md`
4. `docs/autonomous-completion/04-combined-register-index.md`
5. current GitHub history and pull requests
6. a fresh authenticated Edge1 inspection when current runtime state matters

## Guardrails

- Keep credentials, backups, tokens, private keys, raw host evidence, and private records out of Git.
- Do not import unsanitized evidence into the private library.
- Ask before destructive cleanup, DNS, firewall, certificate, public-exposure, billing, regulatory, emergency-calling, or production-traffic changes.
- Keep messaging control disabled until separately approved.
- Treat this register as a recovery index, not proof of current production state.