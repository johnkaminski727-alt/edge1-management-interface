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
| Security Correlation deployment package | Merged in PR #102, main commit `9425d3fc4f3846948ec43590b1f4d15cfc313266` | Awaiting bounded Edge1 installation | CI runs `30425842455` and `30425842388` passed |
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

PR #102 merged the bounded deployment path into `main` at commit `9425d3fc4f3846948ec43590b1f4d15cfc313266`.

The package:

- validates repository, Python, JavaScript, shell, systemd, privacy, and read-only contracts;
- writes only to `/var/www/edge1-status/security/correlation/data`;
- retains empty `CapabilityBoundingSet` and `AmbientCapabilities`;
- publishes the existing `/edge1-status/security-correlation.json` URL through an installer-managed symbolic link;
- captures service/journal evidence before automatic rollback;
- does not modify Suricata, DNS, firewall, Fail2ban, proxy, routing, or reputation-filter controls.

Required CI passed on the exact merged head:

- Edge1 Operator Validation run `30425842455`;
- Validate repository run `30425842388`.

Live deployment remains an explicit operator run:

```bash
cd /opt/edge1-management-interface
git pull --ff-only origin main
sudo bash ./deploy/install-security-correlation-observability.sh
```

## Deferred privileged work

The following remain outside this observability phase and require separate exact authorization and validation:

- Unbound installation or configuration changes;
- RPZ staging into resolver configuration;
- DNS policy activation or resolver reload;
- firewall, nftables, Fail2ban, proxy, routing, or IDS control changes;
- any claim that enforcement is active without a dedicated verifier.

## Next verification sequence

1. Run the bounded Security Correlation installer on Edge1.
2. Verify the correlation timer, service result, JSON privacy contract, console, compatibility symlink, and evidence path.
3. Allow the Network Defense timer to refresh and confirm the correlation source becomes available.
4. Update this register with the successful Security Correlation evidence path.
