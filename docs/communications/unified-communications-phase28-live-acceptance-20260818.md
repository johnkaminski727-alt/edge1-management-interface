# Unified Communications — Phase 28 Live Acceptance Procedure

Date: 2026-08-18
Status: repository procedure; execute only through an authenticated Edge1 operator path

## Purpose

Complete the remaining **live safe-scope** acceptance without using production communications traffic and without silently crossing authentication-policy or provider boundaries.

The repository implementation merged in PR #427 already provides a functional local-native Mail path and the Phase 27 MMS scanner/quarantine implementation. This procedure is for Edge1 deployment evidence only.

## Preconditions

Before any mutation:

1. authenticate to `edge1.ww.cx` through an approved operator connector/shell;
2. record principal, host identity, current UTC time and current `origin/main` SHA;
3. require current main to contain PR #427 merge `e7d7fda638a4f69d68bf54cdebdbee9070143384` or a reviewed descendant;
4. verify live repository worktree/branch and preserve unrelated work;
5. capture `free -h`, `swapon --show`, `df -hT`, relevant service state and listener inventory;
6. inspect actual service users/groups before choosing ownership;
7. create a protected evidence directory and rollback record before changes;
8. never print secret values—record secret **locations/presence only**.

Stop before DNS, firewall, certificate, credential rotation/disclosure, production traffic, quarantine release, carrier/emergency routing, destructive deletion, or any authentication-policy change that lacks explicit approval.

## A. MMS private quarantine + trusted scanner

### Preflight

Inspect without changing:

- `wwcx-messaging-gateway.service` user/group, unit, environment locations and current health;
- current Messaging version/storage/queue state;
- `/usr/bin/clamscan` existence/version;
- local ClamAV signature availability/age;
- any existing private quarantine directory;
- web document roots and mounts;
- package state and memory/disk headroom;
- listeners before change.

If ClamAV is absent, install only the minimum local scanner/signature components when ordinary package installation is permitted and resource-safe. Do not add a public/listening scanner service merely for convenience.

### Private root

Create/verify:

`/var/lib/wwcx-messaging-gateway/private-mms-quarantine`

Requirements:

- outside every web document root;
- actual Messaging service identity owns/accesses it;
- directories no broader than `0700`;
- blob/metadata files no broader than `0600`;
- content-addressed SHA-256 layout remains intact;
- no public listener is introduced.

### Synthetic acceptance

Use repository local-only tooling and generated fixtures. Do not use carrier MMS traffic.

Required cases:

1. clean local sample -> `scanned_clean_held`;
2. locally generated EICAR sample -> `quarantined_malicious`;
3. scanner executable unavailable -> held/fail closed;
4. scanner timeout -> held/fail closed;
5. non-verdict/error exit -> held/fail closed;
6. digest mismatch -> reject/hold;
7. corrupted stored blob/integrity failure -> hold/fail closed;
8. safe storage-failure simulation, if feasible without affecting unrelated data -> no success claim;
9. restart/re-open -> held records/blobs persist;
10. clean result -> `release_authorized=false` remains true as a policy invariant.

After tests, verify service health, logs, listeners, permissions, disk/memory and rollback viability. Preserve evidence outside the live repository worktree.

## B. Local-native Mail correspondence deployment

### Preflight

Inspect:

- `wwcx-outbound-mail-gateway.service` identity/unit/current runtime config;
- existing preparation-only HMAC API state;
- existing environment/secret location names only;
- loopback listener `127.0.0.1:8104` or reviewed current equivalent;
- current send/delivery gates; they must remain disabled for this acceptance;
- any existing `/var/lib/wwcx-mail-room` state.

### Private store

Create/verify `/var/lib/wwcx-mail-room` using the reviewed local intake/service ownership model.

Requirements:

- directory no broader than `0700`;
- `correspondence.sqlite3` no broader than `0600`;
- no web-root placement;
- local intake can write only through the operator-reviewed intake identity/path;
- Mail gateway reads via the repository read-only store mode;
- no API endpoint accepts a filesystem path.

### Local RFC822 acceptance

Generate two local RFC822 fixtures only:

- a root message with canonical Message-ID, From/To, timezone-bearing Date, Subject and text/plain body;
- a reply with a distinct Message-ID, In-Reply-To and References pointing to the root.

Optionally include synthetic `X-WWCX-Provider-Message-ID` / `X-WWCX-Provider-Thread-ID` solely to verify preservation; do not call those values provider-production evidence.

Ingest with `tools/mail_local_intake.py` under the reviewed local intake identity.

Verify:

- two records persist;
- one explicit thread is reconstructed;
- source is `local-mailroom-rfc822`;
- scope is `local_native`;
- authoritative is true **for the local-native source**;
- `production_provider_ready=false`;
- content remains untrusted;
- send/mutation remain false;
- malformed/missing IDs fail closed;
- a synthetic/non-authoritative record cannot be read through Private AI;
- restart/re-open preserves records/thread.

## C. Correspondence API and BigBird

### Authentication-policy gate

The repository intentionally does not add `wwcx-private-ai` to the deployed HMAC allowlist.

Before live registration, obtain explicit approval for the authentication-policy change. If approval is absent:

- do not modify the allowlist;
- do not reuse `wwcx-website-admin` for BigBird;
- stop only this registration step and continue all other permitted acceptance work.

With explicit approval:

1. register only `wwcx-private-ai` using the existing secret location/mechanism; never disclose the secret;
2. keep the API loopback-only;
3. enable local correspondence reads only after the private store has accepted local-native records;
4. verify unsigned request -> rejected;
5. verify `wwcx-website-admin` signed request to correspondence endpoint -> rejected;
6. verify `wwcx-private-ai` signed status/message/thread -> accepted;
7. verify replayed nonce -> rejected;
8. verify missing/invalid IDs -> fail closed;
9. verify body text cannot grant scopes/tools;
10. verify BigBird exposes only `mail.status.read`, `mail.correspondence.read`, and `mail.draft.prepare` for this integration;
11. verify draft remains `prepared_not_sent` and no send/generic-execution/quarantine-release capability appears.

Record exact runtime version, service state, listener, capability list and rollback.

## D. Shared-system regressions

After permitted changes, recheck without generating production traffic:

- Messaging Gateway health/readiness and PostgreSQL durable state;
- outbound Messaging queue state/worker gates from PR #426;
- BigBird existing accepted read-only Messaging capabilities;
- Communications workspace active, loopback-only, POST blocked;
- Relay snapshot/feed present and untrusted-content semantics preserved;
- Voice/SIP existing read-only surface responsive without calls/routes/trunks/dialplan changes;
- no new public management/scanner/mail listener;
- no unexpected service failures or new OOM evidence.

## E. Provider-native Mail remains separate

Local-native acceptance does not prove provider mailbox readiness.

Only promote records/source to `production_native` after an explicitly authorized native mailbox/MTA/provider source supplies real bodies and stable native IDs and passes bounded read-only acceptance.

Do not alter MX/SPF/DKIM/DMARC, provider credentials, forwarding or production mail routing as part of this procedure without separate authorization.

## Completion evidence

Record:

- authenticated principal/host/time;
- starting and final main SHA;
- backups/checkpoints;
- service users/groups;
- permission checks;
- scanner/signature versions/status without secret data;
- synthetic acceptance results;
- API/auth rejection/acceptance results;
- service/listener/health regression results;
- rollback locations;
- exact blocked boundary if BigBird HMAC registration or provider-native source remains unapproved.

Only after actual live evidence should readiness fields be promoted. Green repository CI alone is not live Edge1 acceptance.
