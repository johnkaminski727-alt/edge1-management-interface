# Phase 3 private staging and rollback

This runbook prepares and verifies the messaging gateway privately without authorizing a carrier, public webhook, DID, credentials, billing, or live SMS/MMS traffic.

## Preconditions

1. Start from an immutable reviewed repository revision with exact-head CI green.
2. Inspect the live Edge1 checkout/runtime, service state, listeners, database target, current migration level, and dirty state before changing anything.
3. Preserve unrelated concurrent work. Never reset or clean a shared checkout.
4. Create timestamped backups of every affected configuration/runtime file and a database backup suitable for schema recovery.
5. Record the pre-change service/listener/configuration digest and rollback location.

## Private staging invariants

The staged gateway must retain all of the following:

- no registered real-carrier adapter;
- no carrier credentials or DIDs;
- no public webhook exposure;
- `WWCX_OUTBOUND_WORKER_ENABLED=false` except during an explicit bounded simulator acceptance;
- simulator outbound disabled by default;
- outbound provider allowlist restricted to simulator;
- outbound policy disabled/empty by default outside the isolated simulator acceptance configuration;
- management mutation controls disabled unless an already-approved private control policy explicitly enables them;
- no DNS, firewall, TLS/certificate, Asterisk/FreePBX routing, or production-traffic changes;
- MMS release remains unauthorized.

## Apply procedure

1. Verify the reviewed revision and migration checksums.
2. Back up PostgreSQL before applying additive messaging migrations.
3. Apply migrations in order and stop on any error. Do not manually skip a failed migration.
4. Install/update the private gateway runtime from the reviewed revision without broadening listeners or reverse-proxy exposure.
5. Keep the outbound worker disabled.
6. Start/restart only the directly affected messaging gateway service if required by the accepted deployment method.
7. Verify health/readiness and read-only management status.
8. Verify the effective provider registry contains only `simulator`.
9. Verify worker disabled state, global pause state, queue counts, compliance state, and MMS quarantine state.

## Simulator acceptance

Use only synthetic destinations and the simulator provider.

Validate, at minimum:

- duplicate inbound provider events are idempotent;
- webhook provider identity and direction confusion fail closed;
- STOP suppresses subsequent outbound work;
- HELP is audited without changing suppression;
- START removes only keyword-derived suppression and preserves unrelated/manual suppression;
- stale/out-of-order STOP/START cannot overwrite newer consent state;
- unauthorized sender and disallowed destination attempts are blocked;
- hourly/daily volume reservation is concurrency-safe;
- global pause blocks intake/submission as designed;
- unsupported MMS remains quarantined;
- uncertain provider outcomes are not blindly replayed;
- read-only management surfaces expose no media URLs, secrets, or mutation authority.

A bounded one-shot simulator worker may be enabled only for the duration of the isolated acceptance, then disabled again. Do not introduce continuous worker mode.

## Post-apply verification

Capture:

- deployed revision;
- migration level;
- health/readiness result;
- provider registry;
- worker enabled/disabled state;
- relevant service and listener state;
- queue/compliance/quarantine summaries;
- focused and integration test results;
- exact-head CI run identifiers;
- backup and rollback locations.

Confirm unrelated Edge1 services and listeners retain their pre-change state.

## Rollback

Rollback is backup-first and preserves evidence.

1. Disable any bounded simulator worker invocation and keep carrier/public traffic absent.
2. Stop only the directly affected gateway runtime if rollback requires it.
3. Restore the prior reviewed runtime/configuration from the timestamped backup.
4. If schema rollback is genuinely required, restore the pre-migration database backup rather than attempting destructive ad-hoc DDL. Preserve the failed/new database separately for evidence when feasible.
5. Start the prior gateway runtime and verify health/readiness.
6. Re-check listeners, provider registry, worker state, pause state, and unrelated services against the recorded pre-change evidence.
7. Record the rollback result and retain both the change and rollback evidence.

## Hard stop

Stop before any carrier credentials, paid service, DID provisioning, public webhook exposure, DNS/firewall/certificate/authentication-policy change, production telephony routing change, or live SMS/MMS traffic. Those are separate authorization gates.
