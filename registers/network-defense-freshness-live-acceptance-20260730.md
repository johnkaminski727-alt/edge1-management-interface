# Network Defense Freshness Live Acceptance

Date: 2026-07-30  
Classification: internal operations; no credentials or raw alert data  
Host: `edge1.ww.cx`  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Accepted repository revision: `a06f035e7fcf933a03ec752c66ce0261c5a65ba7`

## Evidence basis

This register records an authenticated operator session supplied through the project conversation. The operator connected by SSH as `wwadmin`, used the documented `sudo` path, and ran the repository-provided preflight and bounded activation scripts. No password or secret material is recorded here.

## Attempt 1: read-only preflight and safe validation stop

The checkout was fast-forwarded from `d1a6a94` to `06d5887`, remained on clean `main`, and the completion preflight passed.

Protected preflight evidence:

```text
/var/lib/wwcx-deployment-evidence/edge1-project-completion-preflight/20260730T193415Z
```

The preflight reported that no Apache, authentication, route, listener, firewall, DNS, or public files were changed.

The first freshness activation then stopped during repository validation before the script set `MUTATION_STARTED=1`. The existing test `tests/test_network_defense_runtime_wiring.py` still required the nftables exporter directly in the systemd unit even though the accepted deployment contract used `network_defense_freshness_exporter.py` as a wrapper over the nftables-aware chain. Because validation failed before mutation, no service unit or Network Defense status snapshot was installed or replaced.

## Corrective repository change

PR #136, **Fix Network Defense freshness runtime validation**, updated the stale test to verify the complete wrapper chain and the 600-second policy without changing a service unit, exporter, deployment script, route, firewall, DNS, authentication, listener, or public file.

- Exact corrective head: `ea4ad48daf51aab5bbb2fbdf90b0a1767eefe353`
- `Validate repository` run 636: success
- `Edge1 Operator Validation` run 468: success
- Merged revision: `a06f035e7fcf933a03ec752c66ce0261c5a65ba7`

## Attempt 2: successful bounded activation

The Edge1 checkout fast-forwarded from `06d5887` to `a06f035` and remained on clean `main`. The complete Network Defense validation suite passed, including runtime wiring, deployment, DNS policy, Spamhaus, Fail2ban, nftables, and freshness-policy tests.

The bounded activation completed successfully and reported:

```json
{
  "dns_enforcement_enabled": false,
  "dns_policy_state": "not_staged",
  "network_stale_after_seconds": 600,
  "ok": true,
  "overall_state": "limited",
  "traffic_controls_changed": false,
  "verified_enforcement_count_after": 1,
  "verified_enforcement_count_before": 1
}
```

Protected activation evidence:

```text
/var/lib/wwcx-deployment-evidence/network-defense-freshness/20260730T195031Z
```

The activation footer confirmed that timer state, enforcement count, DNS policy, and traffic-control state were unchanged. The operator transcript reported successful completion and no rollback.

## Accepted live state

| Control | Accepted result |
| --- | --- |
| Network-source stale threshold | `600` seconds |
| Network Defense overall state | `limited` |
| Verified enforcement count | `1` before and after |
| DNS policy state | `not_staged` |
| DNS enforcement | `false` |
| Traffic controls changed | `false` |
| Timer enabled/active state | Unchanged |
| Repository branch | Clean `main` |
| Live revision | `a06f035e7fcf933a03ec752c66ce0261c5a65ba7` |
| Rollback | Not reported; activation completed successfully |

## Scope and boundaries

This acceptance covers only the existing Network Defense observability service-unit update and one-shot export performed by `deploy/activate-network-defense-freshness.sh`.

It does not authorize or claim:

- minimized-summary publication under `/var/www`;
- Apache alias, header, authentication, proxy, or route changes;
- detailed-artifact removal;
- protected Suricata-retention runtime deployment;
- certificate, listener, DNS, firewall, or production-traffic changes;
- deletion of retained status, report, incident, or evidence data.
