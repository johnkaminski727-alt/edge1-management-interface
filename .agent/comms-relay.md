# Edge1 Communications Relay State

Last repository validation: 2026-08-15  
Live Edge1 acceptance: 2026-08-15 18:31 UTC  
Founder account activation: 2026-08-15 18:37 UTC  
Automatic ingestion activation: 2026-08-15 19:19 UTC  
Current accepted live revision: `359eb977cd8bcc4c986fe688b934303cb53c23d6`

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
- Live activation confirmed `127.0.0.1:8099` is assigned to the WW.CX telephony analytics API; relay control uses dedicated loopback port `8100`.
- Candidate configuration apply/rollback preserves the live config owner, group and mode.

## Live accepted state

- Service: `edge1-comms-relay.service`.
- systemd: enabled and active.
- IRC: `127.0.0.1:16667`.
- NNTP: `127.0.0.1:1119`.
- Control/API: `127.0.0.1:8100`.
- Telephony analytics preserved on `127.0.0.1:8099` and independently healthy.
- Network exposure remains disabled.
- Bundled IRC/NNTP/control smoke tests passed after deployment and ingestion activation.
- Control `/healthz` returned `status: ok`, version `1.0.0`.
- Initial relay deployment evidence: `/var/lib/wwcx-deployment-evidence/comms-relay/20260815T183129Z`.
- Automatic-ingestion activation evidence: `/var/lib/wwcx-deployment-evidence/comms-relay/auto-ingest-20260815T191918Z`.
- Automatic-ingestion code deployment evidence: `/var/lib/wwcx-deployment-evidence/comms-relay/20260815T191922Z`.

## Founder identity

- Local relay login: `john`.
- Account is enabled with role `founder`.
- Founder super-role behavior was verified against the live account.
- IRC SASL PLAIN authentication succeeded against the live IRC listener.
- NNTP AUTHINFO authentication succeeded against the live NNTP listener.
- Founder-account evidence: `/var/lib/wwcx-deployment-evidence/comms-relay/founder-account-20260815T183745Z`.
- No password, password hash, secret, credential, database copy, or unredacted authentication material is stored in this repository.

## Automatic NNTP ingestion — live

- Controlled automatic article ingestion is active on Edge1.
- Accepted sources are local-only:
  - `wwcx-bootstrap` creates stable one-time introduction articles for the seven seeded `wwcx.*` groups;
  - `edge1-repository` monitors local `/opt/edge1-management-interface` `main` and posts eligible commit articles into `wwcx.projects.edge1`.
- Scheduled interval: 900 seconds (15 minutes).
- Startup delay: 5 seconds.
- Per-run item budget: 25.
- The live dry run predicted 15 initial candidates: seven bootstrap articles and eight repository articles.
- The first automatic live run created exactly 15 articles and recorded outcome `ok`.
- All 15 articles were verified against `ingest_items` for automated-source provenance and deterministic Message-IDs.
- An immediate second run produced zero candidates and created zero articles, verifying deduplication/idempotency.
- Current initial group counts after activation: one article each in `wwcx.announce`, `wwcx.general`, `wwcx.projects.bigbird`, `wwcx.security`, `wwcx.telecom`, and `wwcx.test`; nine articles in `wwcx.projects.edge1`.
- SQLite `ingest_items` and `ingest_state` preserve deduplication and cursor state independently of article retention.
- Git execution is shell-free, uses `/usr/bin/git`, a restricted environment, validated refs, an absolute root-controlled repository path, and an explicit read-only `safe.directory` override.
- No external RSS/Atom source, NNTP peer, public listener, federation, or automatic IRC mirroring is enabled.
- Detailed acceptance record: `docs/communications/edge1-comms-relay-ingestion-live-acceptance-20260815.md`.

## Safe default listeners

- IRC `127.0.0.1:16667`
- NNTP `127.0.0.1:1119`
- control `127.0.0.1:8100`

No DNS, firewall, certificate, public listener or federation change is part of this accepted deployment.

## Remaining privileged gates

The private loopback Edge1 Communications Relay, local founder identity, bootstrap article seeding, and controlled local repository ingestion are complete and live. Internet exposure remains a separate privileged change requiring explicit authorization and independent TLS, DNS, firewall, abuse-policy, monitoring and client-compatibility validation. Federation and NNTP peering remain disabled unless separately designed and approved. External account onboarding, external RSS/Atom feeds, other Internet content sources, and automatic IRC-to-NNTP mirroring remain separately governed changes.
