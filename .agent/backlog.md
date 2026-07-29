# Backlog

## Ready

1. Merge the bounded Security Correlation deployment package after required CI succeeds.
2. Deploy Security Correlation on Edge1 with `sudo bash ./deploy/install-security-correlation-observability.sh`.
3. Verify live service/timer state, privacy contract, browser endpoint, compatibility symlink, and evidence directory.
4. Confirm the next Network Defense refresh reports the correlation source as available.
5. Update `registers/security-observability-register-20260729.md` and `.agent/current-state.md` with the live correlation evidence path.

## Safe follow-up design work

- Add read-only normalized firewall counters and service posture without publishing the full ruleset.
- Add read-only Fail2ban jail health and aggregate ban counts without client-identifying raw logs.
- Add a dedicated Spamhaus live-state verifier that distinguishes feed readiness from active nftables enforcement.
- Review whether Network Defense source freshness thresholds need per-source tuning after correlation is live.

## Explicitly deferred

Requires exact production authorization and separate rollback/validation plans:

- Unbound or resolver configuration changes;
- RPZ inclusion, activation, reload, or DNS answer changes;
- firewall, nftables, Fail2ban, proxy, routing, or IDS control changes;
- any public or production traffic cutover;
- any claim of active enforcement without direct evidence.
