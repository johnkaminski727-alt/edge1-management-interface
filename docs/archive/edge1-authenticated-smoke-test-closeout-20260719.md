# Edge1 Authenticated Smoke-Test Closeout

Date: 2026-07-19
Classification: sanitized operational record
System: `edge1.ww.cx`

## Purpose

This record preserves the non-sensitive results of the authenticated Edge1 read-only smoke test and the bounded corrective follow-up completed on 2026-07-19. Raw command logs remain on Edge1 and are not committed because the temporary smoke-test redactor did not fully mask a synthetic bearer value.

## Authenticated observation

- Host: `edge1.ww.cx`
- Principal: `wwadmin` (`uid=1000`, `gid=1000`)
- Groups: `wwadmin`, `sudo`, `users`
- Non-interactive sudo: unavailable; `sudo -n -l` required a password
- Evidence window: 2026-07-19T18:28:23Z through 2026-07-19T18:28:26Z
- Edge1 evidence directory: `/tmp/edge1-readonly-smoke-20260719T182823Z`

The evidence directory is an ephemeral host-local path, not a repository artifact or durable backup.

## Repository snapshot observed on Edge1

At the smoke-test timestamp, `/opt/edge1-management-interface` reported:

- branch: `main`
- HEAD: `d53354fc44c09c4b732a3f8227b8e6cfd6495dcd`
- worktree: clean
- locally recorded `origin/main` divergence: `0 0`

The divergence result was relative to the existing local remote-tracking reference. The test used `git fetch --dry-run`, so it was not proof that the checkout matched the latest GitHub commit. GitHub advanced after this observation; this record must not be used as the current repository baseline.

## Service and endpoint findings

| Component | Result | Sanitized evidence |
| --- | --- | --- |
| BigBird AI gateway | Pass | `bigbird-ai-gateway.service` active; listener `127.0.0.1:8787` |
| Numbering node | Pass | `wwcx-numbering-node.service` active; listener `127.0.0.1:8093`; health `ok` |
| Telephony console | Pass | `wwcx-telephony-console.service` active; `GET /api/telephony/status` returned HTTP 200 |
| Asterisk | Pass with management note | Running under `safe_asterisk`; SIP `0.0.0.0:5060/udp`; AMI `127.0.0.1:5038/tcp` |
| Messaging gateway | Warning | No installed `wwcx-messaging-gateway.service`; dashboard remained critical because messaging was inactive |
| MariaDB | Pass with scope warning | Active; socket activation listened on `*:3306`; public ingress blocked by nftables; VPN ingress accepted; all observed DB accounts were `localhost` only |
| Disk and inodes | Pass | Root filesystem 18% used; root inode use 5% |
| Memory | Warning | 3.8 GiB RAM total, 1.8 GiB available; 818 MiB of 1.0 GiB swap used |

## Firewall finding

The nftables input chain used a default-drop policy. Explicit inbound acceptance included loopback, established/related traffic, ICMP, all traffic arriving on `wg0`, WireGuard UDP 51820, and public HTTP/HTTPS. No public allow rule was observed for MariaDB TCP 3306 or SIP UDP 5060.

Consequences at the observation time:

- MariaDB was not shown to be publicly reachable.
- MariaDB was reachable from the trusted WireGuard network because `wg0` input was accepted.
- Existing MariaDB accounts were restricted to `localhost`, so the observed VPN probe remained unauthenticated.
- SIP listened on all host addresses but was protected from ordinary public ingress by the default-drop input policy.

## Corrective follow-up completed

The smoke test discovered that `logrotate.service` failed because the Fail2ban logrotate hook called `fail2ban-client flushlogs` while Fail2ban was disabled and inactive.

The PBX-generated Fail2ban configuration contained a complete `ssh-iptables` jail plus an incomplete Debian default `[sshd]` jail. The following bounded correction was applied by the operator:

1. Created `/etc/fail2ban/jail.d/99-disable-incomplete-sshd.local` with the incomplete `sshd` jail disabled.
2. Validated configuration with `fail2ban-client -t`; result: successful.
3. Enabled and started `fail2ban.service`.
4. Verified seven active jails: `apache-badbots`, `apache-tcpwrapper`, `asterisk-iptables`, `pbx-gui`, `recidive`, `ssh-iptables`, and `vsftpd-iptables`.
5. Verified Fail2ban chains through the `iptables-nft` backend in the nftables ruleset.
6. Started `logrotate.service`; result: `status=0/SUCCESS`.
7. Verified `systemctl --failed`; result: zero failed units.

No production call, message, number-routing, database-grant, DNS, certificate, or customer-traffic change was performed.

## Audit-evidence limitation

The temporary smoke-test wrapper successfully captured command names, arguments, UTC timestamps, exit codes, outputs, and SHA-256 manifests. Its redaction test failed because synthetic authorization values remained visible after the authorization label was masked.

Therefore:

- do not commit or import the raw evidence directory;
- do not treat the temporary script as production audit tooling;
- implement and regression-test persistent redaction before future evidence archival;
- require tests for `Authorization: Bearer`, generic authorization values, token fields, password fields, query parameters, and command arguments.

## Remaining warnings

- Messaging status remains inactive and continues to make the aggregate telephony status critical.
- Swap use was elevated and should be trended rather than treated as an immediate outage.
- MariaDB remains reachable to trusted `wg0` peers through systemd socket activation, although observed accounts are localhost-only.
- Non-interactive sudo is unavailable to the `wwadmin` execution path.
- The persistent, repository-controlled audit redactor remains unimplemented.

## Archive boundary

This closeout is sanitized and suitable for repository retention. It intentionally excludes:

- raw logs and command transcripts;
- credentials, tokens, keys, authentication headers, and private connection data;
- firewall or database dumps;
- customer, carrier, message, or call records;
- claims that the host snapshot is the current GitHub baseline.

## Restore and follow-up

Use these sources in order:

1. `registers/combined-project-register-20260717.md`
2. `registers/edge1-authenticated-smoke-test-register-20260719.md`
3. this closeout record
4. current GitHub history and pull requests
5. a fresh authenticated host inspection when current production state matters
