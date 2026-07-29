# Spamhaus Live-State Verifier Register

Date: 2026-07-29
Classification: internal, sanitized
System: Edge1 / WW.CX Network Defense

## Trigger

Network Defense previously reported Spamhaus only as `feed_ready`. Feed counters were present, but live nftables state required a dedicated table and service check.

## Implemented assets

| Asset | Purpose | State |
| --- | --- | --- |
| `server/spamhaus_live_state_verifier.py` | Read-only nftables and systemd verifier | Merged and deployed |
| `deploy/systemd/wwcx-spamhaus-live-state.service` | Hardened oneshot with bounded `CAP_NET_ADMIN` | Deployed |
| `deploy/systemd/wwcx-spamhaus-live-state.timer` | One-minute refresh schedule | Deployed |
| `/var/lib/bigbird-networking/spamhaus/live-state.json` | Sanitized runtime snapshot | Installer acceptance passed |
| `server/network_defense_exporter.py` | Consumes live-state contract | Deployed |
| `server/network_defense_dns_exporter.py` | Passes verifier path through DNS-aware runtime | Deployed |
| `deploy/install-spamhaus-live-state-observability.sh` | Rollback-safe activation and acceptance | Passed live |

## Contract

- Schema: `wwcx.spamhaus-live-state.v1`.
- Table: `inet bigbird_spamhaus`.
- Required IPv4 assets: populated `drop4`, input and forward chains, and hooked drop rules in both chains.
- Conditional IPv6 assets: if `drop6` is populated, hooked drop rules must exist in both chains.
- Service requirement: `Result=success`, `ExecMainStatus=0`.
- Timer requirement: active and enabled.
- Safety flags: `read_only: true`, `traffic_controls_changed: false`.

## Published fields

Allowed:

- table, set, and chain presence;
- set element counts only;
- chain hook, policy, and priority;
- drop-rule counts only;
- service result and status;
- timer active/enabled state;
- verification state and bounded error labels.

Excluded:

- addresses and set elements;
- full nftables ruleset;
- raw command output;
- payloads and raw logs;
- credentials and private keys.

## Validation and deployment state

| Validation | State |
| --- | --- |
| Representative nftables JSON parsing | Passed |
| Complete IPv4/IPv6 verification | Passed |
| Partial, absent, and unavailable states | Passed |
| Read-only command enforcement | Passed |
| Address and raw-ruleset exclusion | Passed |
| Atomic 0644 publication | Passed |
| Network Defense integration | Passed |
| Hardened unit and capability boundary | Passed |
| Rollback-safe installer | Passed |
| PR #118 exact-head CI | Passed |
| Runtime wording repair PR #119 CI | Passed |
| First live attempt | Failed assertion; rollback passed |
| Corrected live Edge1 deployment | Passed |

## Evidence

Failed and rolled-back attempt:

```text
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180002Z
```

Successful deployment:

```text
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180755Z
```

## Live acceptance state

The installer and Network Defense consistency checks passed, and `traffic_controls_changed` remained false.

The final terminal excerpt did not include the exact value from `acceptance-summary.json`. The exact accepted state remains to be copied from:

```text
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180755Z/acceptance-summary.json
```

Allowed truthful values are `active_verified`, `partial`, `not_present`, and `unavailable`. Do not record `active_verified` without that direct evidence.

## Safety boundary

No Spamhaus list refresh, nftables mutation, firewall mutation, DNS or resolver change, Fail2ban, proxy, routing, IDS, authentication, or traffic-control change was performed.
