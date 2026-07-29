# Fail2ban Live-State Observability

Date: 2026-07-29  
System: Edge1 / WW.CX Network Defense  
Status: implemented; live activation pending merge

## Objective

Publish bounded, current Fail2ban service and jail-health evidence without changing the Fail2ban service, jails, actions, firewall, nftables, DNS, routing, proxy, IDS, authentication, or traffic controls.

The existing Network Defense snapshot could count normalized Fail2ban events, but it could not distinguish absent telemetry from an inactive service, inaccessible control socket, or healthy active jails.

## Contract

Authoritative verifier:

```text
server/fail2ban_live_state_verifier.py
```

Runtime snapshot:

```text
/var/lib/bigbird-security/fail2ban/live-state.json
```

Contract:

```text
wwcx.fail2ban-live-state.v1
```

The verifier executes only:

```text
systemctl show fail2ban.service ...
fail2ban-client status
fail2ban-client status <sanitized-jail-name>
```

No `set`, `start`, `stop`, `reload`, `restart`, `banip`, or `unbanip` command is permitted.

## Published evidence

Allowed:

- service load, active, sub, result, exit, and unit-file states;
- local control-socket reachability boolean;
- sanitized jail names in the private verifier snapshot;
- declared and observed jail counts;
- aggregate and per-jail currently/total failed counts;
- aggregate and per-jail currently/total banned counts;
- bounded state and error labels.

Excluded:

- banned addresses;
- log and journal paths;
- raw `fail2ban-client` output;
- command strings in the published snapshot;
- firewall rules, nftables sets, or packet data;
- credentials and private keys.

Network Defense consumes only aggregate counters and service/socket booleans. Jail records are not copied into the public status snapshot.

## Truthful states

- `active_observed`: service is active, the socket is reachable, and counters were collected for every sanitized reported jail;
- `partial`: some current evidence is available but the complete jail-health contract is not;
- `inactive`: the service is installed but inactive;
- `not_installed`: the service/client is not installed;
- `unavailable`: the service appears active but the local socket query failed.

All states keep:

```json
{
  "enforcement_verified": false,
  "traffic_controls_changed": false
}
```

Jail presence and ban counters do not independently prove that every action is correctly installed or that every packet path is enforced.

## Capability and service boundary

`wwcx-fail2ban-live-state.service` runs as root because the local Fail2ban socket is normally privileged. It receives no Linux capabilities and is restricted to `AF_UNIX`, strict filesystem protection, and write access only under:

```text
/var/lib/bigbird-security/fail2ban
```

`wwcx-network-defense.service` remains capability-free and reads only the sanitized snapshot.

## Scheduling

`wwcx-fail2ban-live-state.timer` refreshes the verifier every minute. Network Defense orders itself after both the Spamhaus and Fail2ban verifier oneshots.

## Activation

After merge:

```bash
cd /opt/edge1-management-interface
git pull --ff-only origin main
sudo bash ./deploy/install-fail2ban-live-state-observability.sh
```

Expected evidence root:

```text
/var/lib/wwcx-deployment-evidence/fail2ban-live-state/<timestamp>
```

The installer validates the repository, backs up affected observability units and snapshots, installs only the verifier units and updated Network Defense unit, captures acceptance evidence, and restores prior observability state on failure. It never starts, stops, reloads, or restarts `fail2ban.service`.

## Safety boundary

This phase makes no Fail2ban jail/action mutation, firewall or nftables mutation, DNS/resolver/RPZ change, routing, proxy, IDS, authentication, reputation-list, or traffic-control change. Any future enforcement change requires separate explicit authorization and rollback/validation planning.
