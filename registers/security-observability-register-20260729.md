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
| Security observability acceptance | PR #105, commit `ac35bc4667222017d946408144a56a60e6c43e60` | Live acceptance passed | `/var/lib/wwcx-deployment-evidence/security-observability-acceptance/20260729T061936Z` |
| Initial acceptance timing attempt | Same read-only verifier | Failed safely before scheduled refresh | `/var/lib/wwcx-deployment-evidence/security-observability-acceptance/20260729T061449Z` |
| DNS Defense policy architecture | PR #96 | Not staged or activated | Runtime reported `dns_policy_state: not_staged` |

## Network Defense live deployment

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

The `limited` state is not a deployment failure. It represents unavailable optional sources, including the intentionally unstaged DNS policy.

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

This was the documented timing condition, not a service deployment or traffic-control failure. The failure was preserved without restarting services or changing DNS, firewall, Fail2ban, proxy, routing, IDS, or reputation-filter controls.

## Final Security observability acceptance

After the scheduled Network Defense timer refresh, the same read-only verifier passed.

Verified terminal result:

```text
Security observability acceptance passed.
Evidence: /var/lib/wwcx-deployment-evidence/security-observability-acceptance/20260729T061936Z
Security Correlation is live and consumed by Network Defense. No traffic controls were changed.
```

Sanitized acceptance summary:

```json
{
  "ok": true,
  "verified_at": "2026-07-29T06:19:36.959113+00:00",
  "read_only": true,
  "traffic_controls_changed": false,
  "correlation": {
    "age_seconds": 51,
    "events": 42,
    "correlations": 0,
    "available_sources": 4,
    "source_count": 4
  },
  "network_defense": {
    "age_seconds": 15,
    "overall_state": "limited",
    "available_sources": 5,
    "source_count": 6,
    "correlation_age_seconds": 35,
    "dns_policy_state": "not_staged",
    "enforcement_enabled": false,
    "traffic_controls_changed": false
  }
}
```

Acceptance proves:

- Security Correlation and Network Defense snapshots were fresh;
- all 4 Correlation sources were available;
- Network Defense consumed the Correlation source and reported it within freshness limits;
- the Correlation privacy and read-only contract remained intact;
- DNS policy remained `not_staged`;
- resolver enforcement remained disabled;
- `traffic_controls_changed` remained false.

The successful `061936Z` evidence is the authoritative acceptance result. The earlier `061449Z` evidence remains retained as a valid safe-failure timing record.

## Repository and validation record

The bounded Security observability sequence was implemented and validated through:

- PR #101 — scoped Network Defense publication repair;
- PR #102 — bounded Security Correlation deployment;
- PR #104 — sanitized Security Controls inspection;
- PR #105 — live Security observability acceptance verifier;
- PR #107 — corrected Network Defense live evidence anchor;
- PR #108 — recorded live Correlation, controls, and initial acceptance timing evidence.

Required CI passed on the exact implementation and evidence heads before merge.

## Completion status

The bounded Security observability deployment, inspection, and live acceptance sequence is complete. No further authenticated Edge1 action is required for this phase.

Raw live JSON, journal output, firewall rules, banned-IP lists, addresses, ports, credentials, and packet data were not committed to the repository.

## Evidence-driven follow-up

The live inspection confirms nftables and Fail2ban posture are readable through the bounded inspector. Optional future work may:

- evaluate periodic sanitized nftables aggregate counts;
- evaluate periodic Fail2ban jail-name and numeric-counter export;
- add a dedicated Spamhaus live-state verifier that distinguishes feed readiness from active nftables enforcement;
- review Network Defense freshness thresholds using observed live correlation timing.

Any periodic exporter remains a separate design decision requiring least-privilege ownership, a constrained systemd sandbox, sanitized schema, backup and rollback, and dedicated acceptance validation.

## Deferred privileged work

The following remain outside this observability phase and require separate exact authorization and validation:

- Unbound installation or configuration changes;
- RPZ staging into resolver configuration;
- DNS policy activation or resolver reload;
- firewall, nftables, Fail2ban, proxy, routing, IDS, or reputation-filter control changes;
- any public or production traffic cutover;
- any claim that enforcement is active without a dedicated verifier.
