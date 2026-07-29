# Spamhaus Live-State Verifier Register

Date: 2026-07-29
Classification: internal, sanitized
System: Edge1 / WW.CX Network Defense

## Trigger

The live Network Defense console reported the Spamhaus component as `feed_ready`. Bounded feed counters were available, but the exporter explicitly stated that live nftables state required a separate table and service check.

The historical Spamhaus runbook records the expected owned table as:

```text
inet bigbird_spamhaus
```

## Implemented assets

| Asset | Purpose | State |
| --- | --- | --- |
| `server/spamhaus_live_state_verifier.py` | Read-only nftables and systemd verifier | Implemented on feature branch |
| `deploy/systemd/wwcx-spamhaus-live-state.service` | Hardened oneshot with bounded `CAP_NET_ADMIN` | Implemented on feature branch |
| `deploy/systemd/wwcx-spamhaus-live-state.timer` | One-minute refresh schedule | Implemented on feature branch |
| `/var/lib/bigbird-networking/spamhaus/live-state.json` | Sanitized runtime snapshot | Pending activation |
| `server/network_defense_exporter.py` | Consumes live-state contract | Updated on feature branch |
| `server/network_defense_dns_exporter.py` | Passes verifier path through DNS-aware runtime | Updated on feature branch |
| `deploy/install-spamhaus-live-state-observability.sh` | Rollback-safe activation and acceptance | Implemented on feature branch |

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

- table/set/chain presence;
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

## Validation state

| Validation | State |
| --- | --- |
| Representative nftables JSON parsing | Implemented |
| Complete IPv4/IPv6 verification | Implemented |
| Partial, absent, and unavailable states | Implemented |
| Read-only command enforcement | Implemented |
| Address and raw-ruleset exclusion | Implemented |
| Atomic 0644 publication | Implemented |
| Network Defense integration | Implemented |
| Hardened unit and capability boundary | Implemented |
| Rollback-safe installer | Implemented |
| Exact-head CI | Pending PR |
| Live Edge1 activation | Pending merge |
| Live `active_verified` acceptance | Pending activation evidence |

## Expected live result

If the historical Spamhaus filter remains loaded and healthy, Network Defense should report:

```json
{
  "components": {
    "spamhaus": {
      "state": "active_verified",
      "enforcement_verified": true
    }
  },
  "summary": {
    "verified_enforcement_count": 1
  },
  "traffic_controls_changed": false
}
```

A different truthful state is acceptable evidence and must not be rewritten as active enforcement.

## Activation

```bash
cd /opt/edge1-management-interface
git pull --ff-only origin main
sudo bash ./deploy/install-spamhaus-live-state-observability.sh
```

Expected evidence root:

```text
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/<timestamp>
```

## Safety boundary

No Spamhaus list refresh, nftables mutation, firewall mutation, DNS or resolver change, Fail2ban, proxy, routing, IDS, authentication, or traffic-control change is included.
