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
| Security Correlation deployment package | PR #102, commit `9425d3fc4f3846948ec43590b1f4d15cfc313266` | Deployed successfully | `/var/lib/wwcx-deployment-evidence/security-correlation/20260729T061441Z` |
| Network Defense observability | PR #101, commit `6255b3f632e51d3662220bbbe426b76cc1d37f52` | Deployed successfully | `/var/lib/wwcx-deployment-evidence/network-defense/20260729T060015Z` |
| Security Controls inspection | PR #104, commit `7b75ac6ae3047e39b3b5395b904eb19071920d3c` | Read-only inspection completed successfully | `/var/lib/wwcx-deployment-evidence/security-controls-inspection/20260729T061447Z` |
| Security observability acceptance | PR #105, commit `ac35bc4667222017d946408144a56a60e6c43e60` | Initial timing attempt failed safely; read-only rerun pending after Network Defense refresh | `/var/lib/wwcx-deployment-evidence/security-observability-acceptance/20260729T061449Z` |
| DNS Defense policy architecture | PR #96 | Not staged or activated | Runtime reported `dns_policy_state: not_staged` |

## Network Defense live acceptance

The operator-run deployment completed successfully on Edge1 after repository validation and runtime verification.

Verified terminal result:

```text
Network Defense observability deployment passed.
Evidence: /var/lib/wwcx-deployment-evidence/network-defense/20260729T060015Z
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

The `limited` state originally reflected unavailable optional sources, especially Security Correlation and staged DNS policy evidence. It was not a deployment failure.

## Failure and rollback evidence

A prior Network Defense deployment attempt failed because the hardened service could not write into the shared `electrum-watch`-owned status root. The installer captured evidence and rolled back successfully:

```text
/var/lib/wwcx-deployment-evidence/network-defense/20260729T051859Z
```

The corrected deployment writes only to a scoped root-owned directory while retaining an empty capability set.

## Security Correlation live deployment

Security Correlation was deployed successfully through the bounded installer.

Verified terminal result:

```text
Security Correlation observability deployment passed.
Evidence: /var/lib/wwcx-deployment-evidence/security-correlation/20260729T061441Z
No IDS, DNS, firewall, proxy, routing, Fail2ban, or reputation-filter controls were changed.
```

Sanitized first snapshot summary:

```json
{
  "ok": true,
  "read_only": true,
  "events": 41,
  "correlations": 0,
  "available_sources": 4
}
```

The zero correlation count is a reported observation, not a validation failure. The service, timer, privacy contract, scoped publication path, and read-only boundary all passed installation checks.

## Security Controls live inspection

The bounded operator-run inspection completed successfully.

Verified terminal result:

```text
Security Controls inspection passed.
Evidence: /var/lib/wwcx-deployment-evidence/security-controls-inspection/20260729T061447Z
No firewall, DNS, routing, IDS, proxy, Fail2ban, or service controls were changed.
```

Sanitized result:

```json
{
  "firewall_readable": true,
  "fail2ban_readable": true,
  "traffic_controls_changed": false
}
```

The retained evidence excludes raw firewall rules, addresses, ports, protocols, packet payloads, banned-IP lists, credentials, and raw command output.

## Initial acceptance timing result

The first read-only acceptance attempt ran immediately after Correlation deployment and before Network Defense completed its next scheduled refresh.

Protected failure evidence:

```text
/var/lib/wwcx-deployment-evidence/security-observability-acceptance/20260729T061449Z
```

The verifier reported:

```text
AcceptanceError: Network Defense has not consumed Security Correlation yet
```

This is the documented timing condition, not a service deployment or traffic-control failure. The failure was preserved without restarting services or changing DNS, firewall, Fail2ban, proxy, routing, IDS, or reputation-filter controls.

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

## Remaining live completion action

Rerun only the verifier after the scheduled Network Defense refresh:

```bash
cd /opt/edge1-management-interface
sudo bash ./tools/security/verify-security-observability-live.sh
```

Expected successful evidence root:

```text
/var/lib/wwcx-deployment-evidence/security-observability-acceptance/<UTC timestamp>/
```

Do not restart or alter traffic controls to force acceptance.

## Evidence-driven follow-up

The live inspection confirms nftables and Fail2ban posture are readable through the bounded inspector. Any periodic exporter remains a separate design decision requiring least-privilege ownership, sandbox, sanitized schema, rollback, and acceptance validation.

Potential follow-up:

- evaluate periodic sanitized nftables aggregate counts;
- evaluate periodic Fail2ban jail-name and numeric-counter export;
- add a dedicated Spamhaus live-state verifier that distinguishes feed readiness from active nftables enforcement;
- review Network Defense freshness thresholds using live correlation timing.

## Deferred privileged work

The following remain outside this observability phase and require separate exact authorization and validation:

- Unbound installation or configuration changes;
- RPZ staging into resolver configuration;
- DNS policy activation or resolver reload;
- firewall, nftables, Fail2ban, proxy, routing, or IDS control changes;
- any claim that enforcement is active without a dedicated verifier.

## Next record update

After the verifier succeeds, append its successful evidence path and sanitized acceptance summary, then mark the remaining `.agent/backlog.md` items complete.
