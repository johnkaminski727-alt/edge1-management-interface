# Fail2ban Live-State Verifier Register

Date: 2026-07-29  
Classification: internal, sanitized  
System: Edge1 / WW.CX Network Defense

## Trigger

Network Defense previously reported Fail2ban from normalized event counts only. That did not directly establish whether the service was installed, active, reachable through its local control socket, or exposing healthy jail counters.

## Implemented assets

| Asset | Purpose | State |
| --- | --- | --- |
| `server/fail2ban_live_state_verifier.py` | Read-only service/socket/jail counter verifier | Implemented on feature branch |
| `server/network_defense_fail2ban_exporter.py` | Public aggregate-only Network Defense integration | Implemented on feature branch |
| `deploy/systemd/wwcx-fail2ban-live-state.service` | Hardened root oneshot with no capabilities | Implemented on feature branch |
| `deploy/systemd/wwcx-fail2ban-live-state.timer` | One-minute refresh schedule | Implemented on feature branch |
| `deploy/systemd/wwcx-network-defense.service` | Orders after verifier and uses final wrapper | Updated on feature branch |
| `deploy/install-fail2ban-live-state-observability.sh` | Rollback-safe activation and evidence capture | Implemented on feature branch |
| `/var/lib/bigbird-security/fail2ban/live-state.json` | Sanitized private runtime snapshot | Pending activation |

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
| Root and jail status parsing | Implemented |
| Jail-name sanitization and count bound | Implemented |
| Aggregate counter calculation | Implemented |
| Address, path, and raw-output exclusion | Implemented |
| Read-only command enforcement | Implemented |
| Atomic publication | Implemented |
| Public aggregate-only integration | Implemented |
| Stale-source downgrade | Implemented |
| Capability-free hardened unit | Implemented |
| Runtime ordering | Implemented |
| Rollback-safe installer | Implemented |
| Exact-head CI | Pending PR |
| Live Edge1 activation | Pending merge |

## Planned activation

```bash
cd /opt/edge1-management-interface
git pull --ff-only origin main
sudo bash ./deploy/install-fail2ban-live-state-observability.sh
```

Expected evidence:

```text
/var/lib/wwcx-deployment-evidence/fail2ban-live-state/<timestamp>
```

A truthful degraded state is acceptable. The installer must not start or modify `fail2ban.service` to improve the result.

## Safety boundary

No Fail2ban jail/action mutation, service start/stop/reload/restart, nftables or firewall mutation, DNS/resolver/RPZ change, routing, proxy, IDS, authentication, reputation-list, or traffic-control change is included.
