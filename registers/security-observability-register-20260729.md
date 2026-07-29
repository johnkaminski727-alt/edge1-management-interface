# Security Observability Register

Date: 2026-07-29
Classification: internal, sanitized
System: Edge1 / WW.CX Security Operations

## Purpose

Record the authoritative repository and live deployment state for Security Operations, Security Correlation, Network Defense, and staged DNS Defense work.

## Current state

| Component | Repository state | Live state | Evidence |
| --- | --- | --- | --- |
| Security Operations console/exporter | Merged | Existing telemetry observed by Network Defense | `/var/www/edge1-status/security-operations.json` observed during deployment diagnostics |
| Security Correlation foundation | Merged in PR #94, merge commit `5b12904ab8b1e6182df167715d7022092a6d27d8` | Not yet deployed as of this register update | Bounded installer prepared on `agent/security-correlation-deployment-20260729` |
| Network Defense observability | Merged through PR #101, main commit `6255b3f632e51d3662220bbbe426b76cc1d37f52` | Deployed successfully | `/var/lib/wwcx-deployment-evidence/network-defense/20260729T053355Z` |
| DNS Defense policy architecture | Merged in PR #96 | Not staged or activated | Runtime reported `dns_policy_state: not_staged` |

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

## Security Correlation deployment readiness

The prepared bounded deployment path:

- validates repository, Python, JavaScript, shell, systemd, privacy, and read-only contracts;
- writes only to `/var/www/edge1-status/security/correlation/data`;
- retains empty `CapabilityBoundingSet` and `AmbientCapabilities`;
- publishes the existing `/edge1-status/security-correlation.json` URL through an installer-managed symbolic link;
- captures service/journal evidence before automatic rollback;
- does not modify Suricata, DNS, firewall, Fail2ban, proxy, routing, or reputation-filter controls.

Live deployment remains an explicit operator run after merge.

## Deferred privileged work

The following remain outside this observability phase and require separate exact authorization and validation:

- Unbound installation or configuration changes;
- RPZ staging into resolver configuration;
- DNS policy activation or resolver reload;
- firewall, nftables, Fail2ban, proxy, routing, or IDS control changes;
- any claim that enforcement is active without a dedicated verifier.

## Next verification sequence

1. Merge the Security Correlation deployment package after CI passes.
2. Run the bounded installer on Edge1.
3. Verify the correlation timer, service result, JSON privacy contract, console, and evidence path.
4. Allow the Network Defense timer to refresh and confirm the correlation source becomes available.
5. Update this register with the successful Security Correlation evidence path.
