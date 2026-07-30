# Fail2ban Live-State Verifier Register

Date: 2026-07-29  
Live acceptance: 2026-07-30  
Classification: internal, sanitized  
System: Edge1 / WW.CX Network Defense

## Trigger

Network Defense previously reported Fail2ban from normalized event counts only. That did not directly establish whether the service was installed, active, reachable through its local control socket, or exposing healthy jail counters.

## Implemented assets

| Asset | Purpose | State |
| --- | --- | --- |
| `server/fail2ban_live_state_verifier.py` | Read-only service/socket/jail counter verifier | Deployed and accepted |
| `server/network_defense_fail2ban_exporter.py` | Public aggregate-only Network Defense integration | Deployed and accepted |
| `deploy/systemd/wwcx-fail2ban-live-state.service` | Hardened root oneshot with no capabilities | Deployed and accepted |
| `deploy/systemd/wwcx-fail2ban-live-state.timer` | One-minute refresh schedule | Enabled and active |
| `deploy/systemd/wwcx-network-defense.service` | Orders after verifier and uses final wrapper | Deployed and accepted |
| `deploy/install-fail2ban-live-state-observability.sh` | Rollback-safe activation and evidence capture | Executed successfully |
| `/var/lib/bigbird-security/fail2ban/live-state.json` | Sanitized private runtime snapshot | Live, root-owned mode `0640` |

## Contract

- Schema: `wwcx.fail2ban-live-state.v1`.
- Read-only commands: `systemctl show`, `fail2ban-client status`, and `fail2ban-client status <sanitized-jail-name>`.
- Jail-name bound: 64 records, names restricted to letters, digits, underscore, dot, and hyphen.
- Published counts: currently/total failed and currently/total banned.
- Safety flags: `read_only: true`, `enforcement_verified: false`, `traffic_controls_changed: false`.

## Privacy boundary

Allowed in the private verifier snapshot:

- sanitized jail names;
- service and socket booleans/status labels;
- aggregate and per-jail counters.

Allowed in public Network Defense:

- aggregate counters only;
- service/socket booleans;
- observed jail count and truthful state.

Excluded everywhere:

- banned IP addresses;
- log paths;
- raw client output;
- published command strings;
- credentials and private keys.

## State model

| State | Meaning |
| --- | --- |
| `active_observed` | Service active, socket reachable, complete sanitized jail counters observed |
| `partial` | Incomplete jail-health evidence |
| `inactive` | Service installed but inactive |
| `not_installed` | Service or client unavailable as an installed component |
| `unavailable` | Active service but socket query unavailable |

No state in this contract is equivalent to packet-enforcement verification.

## Validation state

| Validation | State |
| --- | --- |
| Root and jail status parsing | Passed |
| Jail-name sanitization and count bound | Passed |
| Aggregate counter calculation | Passed |
| Address, path, and raw-output exclusion | Passed |
| Read-only command enforcement | Passed |
| Atomic private publication | Passed |
| Public aggregate-only integration | Passed |
| Stale-source downgrade | Passed |
| Capability-free hardened unit | Passed |
| Runtime ordering | Passed |
| Rollback-safe installer | Passed |
| Edge1 Operator Validation | Passed on PR #122 head |
| Full repository validation | Passed on PR #122 head |
| PR merge | PR #122 merged as `725a09c1c488c2a0cb99931183e535e9fe726894` |
| Live Edge1 activation | Passed |

## Exact live acceptance

Evidence:

```text
/var/lib/wwcx-deployment-evidence/fail2ban-live-state/20260730T004144Z
/var/lib/wwcx-deployment-evidence/fail2ban-live-state/20260730T004144Z/acceptance-summary.json
```

```json
{
  "ok": true,
  "fail2ban_state": "active_observed",
  "fail2ban_health_observed": true,
  "fail2ban_enforcement_verified": false,
  "observed_jails": 7,
  "currently_banned": 0,
  "total_banned": 0,
  "verified_enforcement_count": 1,
  "overall_state": "limited",
  "available_sources": 7,
  "source_count": 8,
  "dns_policy_state": "not_staged",
  "dns_enforcement_enabled": false,
  "traffic_controls_changed": false
}
```

Interpretation:

- Fail2ban service was active and the local socket was reachable.
- All seven sanitized reported jails were observed.
- Current and total banned counters were zero at acceptance time.
- Fail2ban did not add a verified enforcement source; the count of one remains attributable to Spamhaus.
- Network Defense consumed the same aggregate state.
- No traffic-control mutation occurred.

## Safety boundary

No Fail2ban jail/action mutation, service start/stop/reload/restart, nftables or firewall mutation, DNS/resolver/RPZ change, routing, proxy, IDS, authentication, reputation-list, or traffic-control change was performed.
