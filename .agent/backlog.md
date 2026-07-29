# Backlog

## Ready

1. Pull current `main` on Edge1.
2. Deploy Security Correlation with `sudo bash ./deploy/install-security-correlation-observability.sh`.
3. Capture sanitized firewall and Fail2ban posture with `sudo bash ./tools/security/inspect-security-controls.sh`.
4. Run `sudo bash ./tools/security/verify-security-observability-live.sh` to prove Security Correlation is consumed by Network Defense.
5. Update `registers/security-observability-register-20260729.md` and `.agent/current-state.md` with the three new live evidence paths.

## Evidence-driven follow-up

After the Security Controls inspection is available:

- decide whether nftables aggregate counts can be published periodically with a least-privilege service;
- decide whether Fail2ban socket access and jail counters support a safe periodic exporter;
- add a dedicated Spamhaus live-state verifier that distinguishes feed readiness from active nftables enforcement;
- review Network Defense freshness thresholds using actual correlation and control-inspection timing;
- do not create a permanent controls exporter until the live inspection confirms the minimum required permissions and sanitized schema.

## Explicitly deferred

Requires exact production authorization and separate rollback/validation plans:

- Unbound or resolver configuration changes;
- RPZ inclusion, activation, reload, or DNS answer changes;
- firewall, nftables, Fail2ban, proxy, routing, or IDS control changes;
- any public or production traffic cutover;
- any claim of active enforcement without direct evidence.
