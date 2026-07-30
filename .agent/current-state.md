# Current State

Last verified: 2026-07-30 18:43 UTC  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Authoritative branch: `main`  
Latest implementation merge: `711952afb053fa3bd50c390516fa7b58f3943985`  
Implementation PR: `#126`

## Verified live security observability

- Network Defense and Security Correlation are deployed and accepted through `edge1.ww.cx`.
- Security Operations includes accessible Suricata drill-down, last-known-good caching, normalized schema `2.0`, and enriched allowlisted alert fields.
- Spamhaus is accepted as `active_verified` and remains the sole verified enforcement source.
- Fail2ban is accepted as `active_observed`; the service and local socket were healthy and all 7 reported jails were observed.
- General nftables aggregate visibility is accepted as `ruleset_observed`.
- Network Defense remains `limited`, 8 of 9 sources are available, DNS policy is `not_staged`, DNS enforcement is disabled, and traffic controls are unchanged.

## Repository-complete freshness policy

PR #126 merged the schedule-aware Network Defense freshness policy as `711952afb053fa3bd50c390516fa7b58f3943985`.

Evidence:

- `wwcx-operations-network.timer`: 300-second producer interval;
- `wwcx-network-defense.timer`: 60-second interval with up to 10 seconds randomized delay;
- Security observability live acceptance: 600-second default freshness ceiling.

Implemented behavior:

- only the network-source threshold changes from 300 to 600 seconds;
- every other source threshold remains unchanged;
- the capability-free AF_UNIX-only Network Defense service invokes the final freshness wrapper;
- the full freshness -> nftables -> Fail2ban -> DNS exporter chain is validated;
- no timer interval, producer, enforcement state, or privacy contract changes.

## Repository validation

Exact implementation head: `d2c6357cd913fa376f91b27e43081d1b1e37a6d6`

- `Validate repository` run 610: success;
- `Edge1 Operator Validation` run 442: success;
- PR mergeable and zero commits behind `main` before merge;
- no unresolved review threads;
- changed scope limited to the wrapper, one systemd command path, focused and legacy-chain validations, documentation, register, and `.agent` records.

No authenticated Edge1 shell was available in this runtime. No live deployment or live endpoint acceptance is claimed for the freshness change.

## Authoritative live evidence

```text
/var/lib/wwcx-deployment-evidence/security-observability-acceptance/20260729T061936Z
/var/lib/wwcx-deployment-evidence/edge1-status-domain/20260729T064854Z
/var/lib/wwcx-deployment-evidence/suricata-alert-normalization/20260729T082557Z
/var/lib/wwcx-deployment-evidence/suricata-collector-enrichment/20260729T165711Z
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180755Z
/var/lib/wwcx-deployment-evidence/fail2ban-live-state/20260730T004144Z
/var/lib/wwcx-deployment-evidence/nftables-live-state/20260730T090522Z
```

## Next phase

The next safest optional repository item is a protected historical Suricata-retention design with explicit size, time, privacy, authentication, rollback, and acceptance limits. Public `edge1.ww.cx` access-boundary review remains separate.

## Safety boundary

Repository work remains read-only observability only. Live activation requires separate terminal evidence and must not modify traffic controls or protected production boundaries.
