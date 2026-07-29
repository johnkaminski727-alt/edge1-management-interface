# Security Observability Register

Date: 2026-07-29
Classification: internal, sanitized
System: Edge1 / WW.CX Security Operations

## Purpose

Record the authoritative repository and live deployment state for Security Operations, Security Correlation, Network Defense, Security Controls inspection, acceptance verification, and staged DNS Defense work.

## Current state

| Component | Repository state | Live state | Evidence |
| --- | --- | --- | --- |
| Security Operations console/exporter | Merged | Existing telemetry observed by Network Defense | `/var/www/edge1-status/security-operations.json` observed during deployment diagnostics |
| Security Correlation deployment package | PR #102, commit `9425d3fc4f3846948ec43590b1f4d15cfc313266` | Awaiting bounded Edge1 installation | CI `30425842455`, `30425842388` |
| Network Defense observability | PR #101, commit `6255b3f632e51d3662220bbbe426b76cc1d37f52` | Deployed successfully | `/var/lib/wwcx-deployment-evidence/network-defense/20260729T053355Z` |
| Security Controls inspection | PR #104, commit `7b75ac6ae3047e39b3b5395b904eb19071920d3c` | Awaiting read-only Edge1 inspection | CI `30426203898`, `30426203900` |
| Security observability acceptance | PR #105, commit `ac35bc4667222017d946408144a56a60e6c43e60` | Awaiting correlation deployment and timer refresh | CI `30426363318`, `30426363513` |
| DNS Defense policy architecture | PR #96 | Not staged or activated | Runtime reported `dns_policy_state: not_staged` |

## Network Defense live acceptance

The operator-run deployment completed successfully on Edge1 after repository validation and runtime verification.

Verified terminal result:

```text
Network Defense observability deployment passed.
Evidence: /var/lib/wwcx-deployment-evidence/network-defense/20260729T053355Z
DNS enforcement remains disabled; no resolver configuration was installed or reloaded.
```

Verified runtime contract:

```json
{
  "overall_state": "limited",
  "dns_policy_state": "not_staged",
  "enforcement_enabled": false,
  "traffic_controls_changed": false
}
```

The `limited` state reflects unavailable optional sources, especially Security Correlation and staged DNS policy evidence. It is not a deployment failure.

## Failure and rollback evidence

A prior Network Defense deployment attempt failed because the hardened service could not write into the shared `electrum-watch`-owned status root. The installer captured evidence and rolled back successfully:

```text
/var/lib/wwcx-deployment-evidence/network-defense/20260729T051859Z
```

The corrected deployment writes only to a scoped root-owned directory while retaining an empty capability set.

## Security Correlation deployment package

PR #102 merged the bounded deployment path into `main` at commit `9425d3fc4f3846948ec43590b1f4d15cfc313266`.

The package:

- validates repository, Python, JavaScript, shell, systemd, privacy, and read-only contracts;
- writes only to `/var/www/edge1-status/security/correlation/data`;
- retains empty `CapabilityBoundingSet` and `AmbientCapabilities`;
- publishes the existing `/edge1-status/security-correlation.json` URL through an installer-managed symbolic link;
- captures service/journal evidence before automatic rollback;
- does not modify Suricata, DNS, firewall, Fail2ban, proxy, routing, or reputation-filter controls.

## Security Controls inspection package

PR #104 added an operator-run evidence package rather than a permanent service.

It retains only:

- nftables command and service availability;
- aggregate table, chain, rule, set, map, flowtable, and named-counter counts;
- Fail2ban command and service availability;
- jail names and numeric failed/banned counters.

It explicitly excludes raw firewall rules, addresses, ports, protocols, packet payloads, banned-IP lists, credentials, and raw command output. The contract always reports `read_only: true` and `traffic_controls_changed: false`.

## Security observability acceptance package

PR #105 added a read-only verifier that requires:

- correlation and Network Defense timers enabled and active;
- both one-shot services to have completed successfully;
- fresh correlation and Network Defense snapshots;
- the correlation privacy contract intact;
- Network Defense source `correlation` available and not stale;
- DNS enforcement disabled and explicit activation still required;
- `traffic_controls_changed: false`.

It records protected success or failure evidence without restarting services or modifying controls.

## Ordered live completion sequence

```bash
cd /opt/edge1-management-interface
git pull --ff-only origin main
sudo bash ./deploy/install-security-correlation-observability.sh
sudo bash ./tools/security/inspect-security-controls.sh
sudo bash ./tools/security/verify-security-observability-live.sh
```

Expected evidence roots:

```text
/var/lib/wwcx-deployment-evidence/security-correlation/<UTC timestamp>/
/var/lib/wwcx-deployment-evidence/security-controls-inspection/<UTC timestamp>/
/var/lib/wwcx-deployment-evidence/security-observability-acceptance/<UTC timestamp>/
```

If acceptance reports that Network Defense has not consumed correlation yet, preserve the failure evidence and rerun the verifier after the next scheduled timer refresh. Do not restart or alter traffic controls.

## Deferred privileged work

The following remain outside this observability phase and require separate exact authorization and validation:

- Unbound installation or configuration changes;
- RPZ staging into resolver configuration;
- DNS policy activation or resolver reload;
- firewall, nftables, Fail2ban, proxy, routing, or IDS control changes;
- any claim that enforcement is active without a dedicated verifier.

## Next record update

After the ordered live sequence succeeds, append the three evidence paths and sanitized acceptance summary to this register and mark the corresponding `.agent/backlog.md` items complete.
