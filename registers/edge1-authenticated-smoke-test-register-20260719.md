# Edge1 Authenticated Smoke-Test Register

Date: 2026-07-19
Classification: internal, sanitized
Status: corrective follow-up complete; archive-ready with noted residual warnings

## Scope

Authenticated read-only inspection of Edge1 identity, repository state, services, listeners, local HTTP endpoints, host resources, failed units, and audit-evidence behavior, followed by a bounded Fail2ban/logrotate correction performed by the operator.

## Evidence anchors

| Item | Value |
| --- | --- |
| Host | `edge1.ww.cx` |
| Principal | `wwadmin` |
| Smoke-test evidence window | `2026-07-19T18:28:23Z` to `2026-07-19T18:28:26Z` |
| Host-local evidence directory | `/tmp/edge1-readonly-smoke-20260719T182823Z` |
| Observed host checkout HEAD | `d53354fc44c09c4b732a3f8227b8e6cfd6495dcd` |
| Sanitized archive record | `docs/archive/edge1-authenticated-smoke-test-closeout-20260719.md` |

The host-local evidence directory is ephemeral and must not be imported or committed because the temporary redactor failed its synthetic bearer-value test.

## Check register

| Check | Final result | Notes |
| --- | --- | --- |
| Authenticated hostname and principal | Pass | Host and `wwadmin` identity verified |
| Group membership | Pass | `wwadmin`, `sudo`, `users` |
| Non-interactive sudo | Warning | Password required |
| Repository branch and worktree | Pass at observation time | `main`, clean worktree |
| Repository divergence | Qualified pass | `0 0` against existing local `origin/main`; no real fetch |
| BigBird AI gateway | Pass | Active on loopback port 8787 |
| Numbering node | Pass | Active on loopback port 8093; health `ok` |
| Telephony console | Pass | Active; aggregate status endpoint HTTP 200 |
| Asterisk | Pass | Running under `safe_asterisk`; SIP and AMI listeners verified |
| Messaging gateway | Warning | Inactive/absent; aggregate telephony state remains critical |
| MariaDB runtime | Pass | Active and serving FreePBX/Asterisk locally |
| MariaDB public ingress | Pass | Blocked by default-drop nftables input policy |
| MariaDB VPN scope | Warning | `wg0` input accepted; socket activation listens on TCP 3306 |
| MariaDB account scope | Pass | Observed accounts restricted to `localhost` |
| Disk and inode capacity | Pass | 18% root disk use; 5% root inode use |
| Memory | Warning | Elevated swap use; adequate available RAM |
| Fail2ban | Pass after correction | Enabled, active, seven jails verified |
| Logrotate | Pass after correction | Manual service run exited successfully |
| Failed systemd units | Pass after correction | Zero failed units |
| Evidence capture | Pass | Arguments, timestamps, exit codes, outputs, hashes captured |
| Evidence redaction | Failure | Synthetic bearer value remained visible |

## Changes applied outside Git

| Change | State | Rollback |
| --- | --- | --- |
| `/etc/fail2ban/jail.d/99-disable-incomplete-sshd.local` | Applied | Remove file, revalidate, reload/restart Fail2ban only after confirming replacement jail behavior |
| `fail2ban.service` enabled and started | Applied and verified | `systemctl disable --now fail2ban.service` only if a reviewed rollback is required |

The PBX-generated `/etc/fail2ban/jail.local` was not edited.

## Active Fail2ban jails verified

- `apache-badbots`
- `apache-tcpwrapper`
- `asterisk-iptables`
- `pbx-gui`
- `recidive`
- `ssh-iptables`
- `vsftpd-iptables`

The system uses `iptables-nft`; Fail2ban chains were observed in the nftables ruleset.

## Archive readiness

Ready to archive the sanitized project record, subject to these boundaries:

- raw evidence remains host-local and unarchived;
- the temporary smoke-test script is not approved production audit tooling;
- the audit redaction defect remains an open engineering item;
- messaging activation remains a separate project boundary;
- current host state must be re-verified before future operational decisions.

## Open follow-up

| Item | Priority | Approval boundary |
| --- | --- | --- |
| Implement persistent redaction utility and regression tests | High | Routine repository work |
| Trend swap use and identify sustained memory pressure | Medium | Read-only inspection first |
| Decide whether MariaDB should remain VPN-reachable | Medium | Firewall/socket change requires explicit production authorization |
| Complete read-only messaging-status activation | Separate track | Follow existing messaging activation gate |
| Reconcile Edge1 checkout with current GitHub `main` | Medium | Routine fetch/inspection; preserve local work |

## Source of truth

This register records the 2026-07-19 observation and correction. It does not supersede current GitHub history, current Edge1 runtime state, or subsystem-specific registers created after this date.
