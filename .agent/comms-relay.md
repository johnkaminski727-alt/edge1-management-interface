# Edge1 Communications Relay State

Last repository validation: 2026-08-15  
Feature branch: `feature/edge1-comms-relay`

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

## Safe default listeners

- IRC `127.0.0.1:16667`
- NNTP `127.0.0.1:1119`
- control `127.0.0.1:8099`

No DNS, firewall, certificate, public listener or federation change is part of repository completion.

## Remaining live gate

The repository may be merged after CI. Live Edge1 installation/activation must be performed through an authenticated Edge1 execution path and verified with the bundled deployment smoke test. External exposure remains a separate privileged change requiring explicit authorization.
