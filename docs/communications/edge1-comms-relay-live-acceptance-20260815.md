# Edge1 Communications Relay Live Acceptance Record

Date: 2026-08-15  
Host: `edge1.ww.cx`  
Initial accepted revision: `99f16add875bdd6b185821d5491851bba9e12a68`  
Current accepted live revision after ingestion activation: `359eb977cd8bcc4c986fe688b934303cb53c23d6`  
Service: `edge1-comms-relay.service`

## Outcome

The private loopback WW.CX Edge1 Communications Relay 1.0.0 deployment is accepted as live and operational.

The accepted runtime endpoints are:

- IRC: `127.0.0.1:16667`
- NNTP: `127.0.0.1:1119`
- relay control/API: `127.0.0.1:8100`
- existing WW.CX telephony analytics: `127.0.0.1:8099` (preserved)

`network_exposure.enabled` remains `false`; no DNS, firewall, certificate, public listener or federation change has been performed.

## Initial live validation evidence

The attended Edge1 deployment session verified:

- repository `main` fast-forwarded to the initial accepted revision;
- the migrated relay configuration validated successfully with control on port 8100;
- `tests/validate_comms_relay.py` passed production readiness;
- the deployment dry-run completed without changes;
- the transactional installer completed with bundled smoke test passing on attempt 2 of 12;
- `edge1-comms-relay.service` reported both `enabled` and `active`;
- a second independent bundled smoke test passed on attempt 1 of 12;
- IRC, NNTP and relay control listeners were present only on loopback;
- relay `/healthz` returned service `edge1-comms-relay`, status `ok`, version `1.0.0`;
- the existing telephony analytics `/healthz` on 8099 remained `status: ok` and `mode: read_only`.

## Deployment evidence paths

- Initial successful deployment evidence: `/var/lib/wwcx-deployment-evidence/comms-relay/20260815T183129Z`
- Pre-migration config backup: `/var/lib/wwcx-deployment-evidence/comms-relay/control-port-migration-20260815T183128Z/config.before.json`

These paths are on Edge1 and are not copied into the repository.

## Founder identity activation

At 18:37 UTC on 2026-08-15, the first local relay identity was created and verified:

- username: `john`;
- enabled: yes;
- role: `founder`;
- live IRC SASL PLAIN authentication: passed;
- live NNTP AUTHINFO authentication: passed;
- founder authorization semantics: passed;
- post-change bundled relay smoke test: passed;
- relay `/healthz`: remained `status: ok`, version `1.0.0`;
- no service restart was required.

A consistent SQLite backup was created before the account mutation. The sanitized relay audit records the successful `account.add` and subsequent IRC and NNTP authentication events. No password, password hash, database copy, or unredacted credential material is stored in the repository.

Founder activation evidence: `/var/lib/wwcx-deployment-evidence/comms-relay/founder-account-20260815T183745Z`

## Automatic ingestion extension

At approximately 19:19 UTC on 2026-08-15, controlled automatic NNTP population was activated and accepted on the live relay.

Accepted automatic sources:

- `wwcx-bootstrap`: stable one-time group introductions;
- `edge1-repository`: local Edge1 `main` commit articles into `wwcx.projects.edge1`.

The activation used the candidate/running config workflow after a consistent SQLite backup. Config ownership and mode remained `root:wwcx-comms 0640` across apply. The relay restarted cleanly, all listeners remained loopback-only, telephony analytics on 8099 remained healthy, and the bundled smoke test passed.

The initial dry run predicted 15 items; the live startup run created exactly 15. All 15 passed source-provenance verification, and an immediate second run created zero additional articles.

Automatic ingestion interval: 900 seconds (15 minutes).

Detailed acceptance evidence is recorded in:

`docs/communications/edge1-comms-relay-ingestion-live-acceptance-20260815.md`

Live activation evidence root:

`/var/lib/wwcx-deployment-evidence/comms-relay/auto-ingest-20260815T191918Z`

## Resolved activation incident

An earlier activation attempt used relay control port 8099 and failed with `OSError: [Errno 98] Address already in use`. Investigation established that 8099 was already the intended loopback endpoint for the WW.CX telephony analytics API. The relay control default was corrected to 8100 in PR #310. The later deployment used 8100, passed smoke tests, and preserved the 8099 telephony service.

The earlier journal traceback is historical evidence of the superseded configuration, not an error from the accepted deployment.

## Acceptance boundary

Accepted:

- private Edge1 IRC service;
- private Edge1 NNTP reader/poster service;
- shared local identity/policy/storage/audit foundation;
- local `john` founder identity with verified IRC and NNTP authentication;
- loopback read-only control/API;
- hardened systemd deployment;
- tested rollback-capable installer;
- runtime health and protocol smoke verification;
- stable bootstrap/group-introduction article seeding;
- controlled local Edge1 repository commit ingestion into `wwcx.projects.edge1`;
- provenance-aware, deduplicated automatic ingestion every 15 minutes.

Not accepted or enabled by this record:

- Internet-facing IRC or NNTP;
- TLS certificate provisioning;
- DNS changes;
- firewall changes;
- IRC federation/server-to-server operation;
- NNTP peering;
- automatic IRC-to-NNTP mirroring;
- external account onboarding beyond the local founder identity;
- external RSS/Atom or other Internet content sources.

Those remain separately governed future changes.
