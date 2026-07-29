# Security Controls read-only inspection

## Purpose

This package captures sanitized firewall and Fail2ban posture from Edge1 before designing a permanent status exporter or dashboard integration.

It is an evidence-gathering step, not a control-plane deployment. It does not change firewall rules, Fail2ban jails, services, DNS, routing, IDS, proxy configuration, or traffic.

## Data retained

### nftables

- command availability;
- `nftables.service` load, active, substate, enablement and result fields;
- aggregate counts of tables, chains, rules, sets, maps, flowtables and named counters;
- whether the JSON ruleset could be read.

### Fail2ban

- command availability;
- `fail2ban.service` load, active, substate, enablement and result fields;
- jail names;
- per-jail and aggregate numeric failed/banned counters;
- whether status could be read.

## Data deliberately excluded

- raw nftables rules;
- source or destination addresses;
- ports and protocols;
- packet payloads;
- Fail2ban banned-IP lists;
- unrestricted command output;
- credentials, keys or secrets.

The JSON contract always reports:

```json
{
  "read_only": true,
  "traffic_controls_changed": false,
  "privacy": {
    "raw_rules_included": false,
    "addresses_included": false,
    "ports_included": false,
    "packet_payloads_included": false,
    "banned_ip_list_included": false,
    "raw_command_output_included": false
  }
}
```

## Validation

```bash
bash tools/security/validate-security-controls-inspection.sh
```

Validation covers Python syntax, parser tests, degraded execution when tools or privileges are unavailable, shell syntax, privacy flags and the static no-mutation command boundary.

## Edge1 inspection

After pulling the merged package on Edge1:

```bash
cd /opt/edge1-management-interface
git pull --ff-only origin main
sudo bash ./tools/security/inspect-security-controls.sh
```

The wrapper is restricted to `edge1` or `edge1.ww.cx`. It validates the package, records the repository revision and command plan, executes the sanitized inspector and writes protected evidence under:

```text
/var/lib/wwcx-deployment-evidence/security-controls-inspection/<UTC timestamp>/
```

Expected terminal ending:

```text
Security Controls inspection passed.
Evidence: /var/lib/wwcx-deployment-evidence/security-controls-inspection/<UTC timestamp>
No firewall, DNS, routing, IDS, proxy, Fail2ban, or service controls were changed.
```

## Decision gate after inspection

Use the sanitized evidence to decide whether to build a periodic exporter. A permanent service should not be created until the live inspection confirms:

- which commands and units exist;
- the minimum read capability needed for nftables;
- Fail2ban socket accessibility;
- stable output schemas;
- appropriate freshness thresholds;
- that no sensitive values appear in the sanitized JSON.

Any later service activation remains a separate bounded deployment with explicit capability, rollback and evidence review.
