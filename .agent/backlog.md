# Backlog

## Ready

- [x] Pull current `main` on Edge1.
- [x] Deploy Security Correlation with `sudo bash ./deploy/install-security-correlation-observability.sh`.
- [x] Capture sanitized firewall and Fail2ban posture with `sudo bash ./tools/security/inspect-security-controls.sh`.
- [ ] Rerun `sudo bash ./tools/security/verify-security-observability-live.sh` after the scheduled Network Defense refresh proves Security Correlation is consumed.
- [ ] Record the successful acceptance evidence path and final sanitized summary.

## Evidence-driven follow-up

The live Security Controls inspection confirmed both nftables and Fail2ban posture are readable through the bounded inspector. Follow-up design work may now:

- decide whether nftables aggregate counts can be published periodically with a least-privilege service;
- decide whether Fail2ban socket access and jail counters support a safe periodic exporter;
- add a dedicated Spamhaus live-state verifier that distinguishes feed readiness from active nftables enforcement;
- review Network Defense freshness thresholds using actual correlation and control-inspection timing;
- avoid creating a permanent controls exporter until its minimum permissions, ownership, sandbox, sanitized schema, rollback, and acceptance checks are defined.

## Explicitly deferred

Requires exact production authorization and separate rollback/validation plans:

- Unbound or resolver configuration changes;
- RPZ inclusion, activation, reload, or DNS answer changes;
- firewall, nftables, Fail2ban, proxy, routing, or IDS control changes;
- any public or production traffic cutover;
- any claim of active enforcement without direct evidence.
