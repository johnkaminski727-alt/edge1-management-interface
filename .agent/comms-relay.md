# Edge1 Communications Relay State

Last repository validation: 2026-08-15  
Live Edge1 acceptance: 2026-08-15 18:31 UTC  
Founder account activation: 2026-08-15 18:37 UTC  
Production revision: `99f16add875bdd6b185821d5491851bba9e12a68`

## Production-ready repository state

- IRC and NNTP services share durable local identity, policy, audit and SQLite storage.
- IRC supports SASL PLAIN, authenticated registration, channels, messaging, topics, NAMES/WHO, operator KICK and moderated `+m` channels.
- NNTP supports authenticated reader/poster operation, overview/navigation, durable articles, moderated groups and server-side authenticated identity marking.
- Federation is denied by policy and implementation.
- Public plaintext protocol binds are rejected; the control API is loopback-only.
- Runtime defenses include total/per-peer connection caps, per-connection command token buckets, cross-reconnect authentication throttling and idle timeouts.
- Password hashes use PBKDF2-HMAC-SHA256 with per-account salt and per-account iteration metadata; the production default is 600,000 iterations and 12-character minimum passwords.
- SQLite uses WAL mode, busy timeout, foreign keys, explicit transactions and restrictive database permissions.
- NNTP, IRC-history and audit retention are enforced at startup and periodically.
- Control API has `/healthz`; mutation methods remain disabled.
- The systemd service has resource ceilings and a restrictive sandbox.
- Deployment is dry-run-first, requires a clean `main` checkout, supports expected-commit pinning, records evidence, smoke-tests activation and rolls back unit/config/service state on failure.
- Live activation on 2026-08-15 confirmed that `127.0.0.1:8099` is already assigned to the WW.CX telephony analytics API. The relay control endpoint therefore uses dedicated loopback port `8100`.

## Live accepted state

- Service: `edge1-comms-relay.service`
- systemd: enabled and active.
- IRC: `127.0.0.1:16667`.
- NNTP: `127.0.0.1:1119`.
- Control/API: `127.0.0.1:8100`.
- Telephony analytics preserved on `127.0.0.1:8099` and independently healthy.
- Network exposure remains disabled.
- Bundled IRC/NNTP/control smoke test passed after activation.
- Control `/healthz` returned `status: ok`, version `1.0.0`.
- Deployment evidence directory: `/var/lib/wwcx-deployment-evidence/comms-relay/20260815T183129Z`.
- Pre-migration configuration backup: `/var/lib/wwcx-deployment-evidence/comms-relay/control-port-migration-20260815T183128Z/config.before.json`.
- The earlier 18:23 UTC `Address already in use` failure belongs to the superseded 8099 control-port attempt; the corrected 18:31 UTC deployment passed smoke tests and remained active during acceptance verification.

## Founder identity activation

- Local relay login: `john`.
- Account is enabled with role `founder`.
- Founder super-role behavior was verified against the live account.
- IRC SASL PLAIN authentication succeeded against the live IRC listener.
- NNTP AUTHINFO authentication succeeded against the live NNTP listener.
- Relay health and the bundled smoke test remained green after account creation; no service restart was required.
- The sanitized audit trail recorded successful `account.add`, IRC authentication, IRC connect/disconnect, and NNTP authentication events.
- Founder-account evidence directory: `/var/lib/wwcx-deployment-evidence/comms-relay/founder-account-20260815T183745Z`.
- A consistent pre-account SQLite backup was captured in that evidence directory before mutation.
- No password, password hash, secret, credential, database copy, or unredacted authentication material is stored in this repository.

## Safe default listeners

- IRC `127.0.0.1:16667`
- NNTP `127.0.0.1:1119`
- control `127.0.0.1:8100`

No DNS, firewall, certificate, public listener or federation change is part of this accepted deployment.

## Remaining privileged gates

The private loopback Edge1 Communications Relay deployment and local founder identity activation are complete. Internet exposure remains a separate privileged change requiring explicit authorization and independent TLS, DNS, firewall, abuse-policy, monitoring and client-compatibility validation. Federation and NNTP peering remain disabled unless separately designed and approved. External account onboarding and production message seeding also remain separately governed changes.
