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

## Automatic NNTP ingestion implementation

- Controlled automatic article ingestion is implemented on `feature/comms-relay-auto-ingest` pending CI, merge, and live activation.
- The initial source set is deliberately local-only: stable bootstrap/group-introduction articles plus the local Edge1 repository `main` history into `wwcx.projects.edge1`.
- Every generated article carries automated-source provenance and uses a deterministic Message-ID derived from source name plus source-item ID.
- SQLite `ingest_items` and `ingest_state` tables provide deduplication and cursor state; article retention does not erase the source ledger.
- The daemon runs ingestion after a bounded startup delay and then at a configured interval. Ingestion errors are audited without stopping IRC, NNTP, or control services.
- Git execution is shell-free, uses `/usr/bin/git`, a strict environment, validated refs, an absolute root-controlled repository path, and an explicit read-only `safe.directory` override.
- No external RSS/Atom source, NNTP peer, public listener, federation, or automatic IRC mirroring is enabled by this implementation.
- Live activation requires a consistent pre-change SQLite backup, candidate configuration review/apply, relay restart through the transactional installer, protocol smoke tests, ingestion dry-run, actual ingest run, and article/provenance verification.

## Safe default listeners

- IRC `127.0.0.1:16667`
- NNTP `127.0.0.1:1119`
- control `127.0.0.1:8100`

No DNS, firewall, certificate, public listener or federation change is part of this accepted deployment.

## Remaining privileged gates

The private loopback Edge1 Communications Relay deployment and local founder identity activation are complete. Automatic ingestion is repository-implemented but not yet live until the feature is merged and the attended Edge1 activation passes. Internet exposure remains a separate privileged change requiring explicit authorization and independent TLS, DNS, firewall, abuse-policy, monitoring and client-compatibility validation. Federation and NNTP peering remain disabled unless separately designed and approved. External account onboarding and external content-source activation also remain separately governed changes.
