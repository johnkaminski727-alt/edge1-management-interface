# Edge1 Communications Relay State

Last reconciled: 2026-08-17  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Authoritative repository branch: `main`  
Service: `edge1-comms-relay.service`  
Service version: `1.0.0`

## Current accepted production state

The Edge1 Communications Relay is live and accepted as a private-first communications service.

- IRC: `127.0.0.1:16667`.
- NNTP: `127.0.0.1:1119`.
- Control/API/News Reader: `127.0.0.1:8100`.
- Telephony analytics remains separate on `127.0.0.1:8099`.
- `network_exposure.enabled` remains false.
- systemd service is enabled and active at the accepted runtime state.
- control `/healthz` returned `status: ok`, version `1.0.0` at final acceptance and archive-seal preflight.
- mutation methods on the control API remain blocked with HTTP 405.
- federation is disabled.

The accepted production checkout for News Reader v2 is deliberately isolated from later unrelated remote `main` changes:

- branch: `deploy/private-nntp-news-reader-v2-20260817`;
- head: `974c7141e18deac92671f81fb1bd3c3ed02a6c68`;
- result: `NEWS_READER_V2_DEPLOYMENT=PASS`.

Do not move the live checkout to current remote `main` merely to reconcile repository history. Separate work on `main` requires its own production review.

## Core relay capabilities

- IRC and NNTP share durable local identity, policy, audit and SQLite storage.
- IRC supports SASL PLAIN, authenticated registration, channels, messaging, topics, NAMES/WHO, operator KICK and moderated `+m` channels.
- NNTP supports authenticated reader/poster operation, overview/navigation, durable articles and moderated groups.
- authenticated NNTP posts receive server-side canonical WW.CX identity marking.
- public plaintext protocol binds are rejected unless the separately gated exposure/TLS policy is satisfied.
- control/API is always loopback-only and read-only.
- runtime defenses include total/per-peer connection caps, command token buckets, cross-reconnect authentication throttling and idle timeouts.
- password hashes use PBKDF2-HMAC-SHA256 with per-account salt and iteration metadata; production default is 600,000 iterations and 12-character minimum passwords.
- SQLite uses WAL mode, busy timeout, foreign keys, explicit transactions and restrictive permissions.
- NNTP, IRC-history and audit retention are enforced at startup and periodically.
- candidate configuration apply/rollback preserves live config owner, group and mode.

## Founder identity

- local relay login: `john`;
- account enabled with role `founder`;
- founder super-role behavior accepted live;
- IRC SASL PLAIN authentication accepted live;
- NNTP AUTHINFO authentication accepted live.

Founder-account evidence:

`/var/lib/wwcx-deployment-evidence/comms-relay/founder-account-20260815T183745Z`

No password, password hash, credential value, database copy, or unredacted authentication material belongs in repository documentation.

## Automatic ingestion — accepted live

Automatic ingestion runs inside `edge1-comms-relay.service` on the existing 900-second cycle with a startup delay and per-run item budget. A per-database lock prevents overlapping runs.

Accepted source order:

1. `wwcx-bootstrap`;
2. `eternal.comp.lang.python`;
3. `eternal.news.admin.peering`;
4. `edge1-repository`.

### Local sources

- `wwcx-bootstrap` creates stable one-time introduction articles for groups discovered by the relay.
- `edge1-repository` monitors the local Edge1 repository and posts eligible commit articles into `wwcx.projects.edge1`.

### Eternal September source 1

- source: `eternal.comp.lang.python`;
- upstream: `news.eternal-september.org:563`;
- upstream group: `comp.lang.python`;
- local group: `usenet.comp.lang.python`;
- TLS required;
- retention 3650 days;
- max article bytes 262144;
- initial items 8;
- scan limit 10;
- accepted external items: 8;
- accepted bootstrap introduction: 1 (`usenet.comp.lang.python:v1`);
- duplicate external source IDs: 0.

Evidence:

`/var/lib/wwcx-deployment-evidence/comms-relay/eternal-september-live-20260815T233435Z`

### Eternal September source 2

- source: `eternal.news.admin.peering`;
- upstream: `news.eternal-september.org:563`;
- upstream group: `news.admin.peering`;
- local group: `usenet.news.admin.peering`;
- TLS required;
- retention 3650 days;
- max article bytes 262144;
- initial items 8;
- scan limit 10;
- accepted external items: 8;
- accepted bootstrap introduction: 1 (`usenet.news.admin.peering:v1`);
- duplicate external source IDs: 0;
- wrong-group/orphan/bad-provenance/unexpected-provenance counts: 0 at acceptance;
- ingestion errors since activation: 0 at acceptance.

Evidence:

`/var/lib/wwcx-deployment-evidence/comms-relay/eternal-news-admin-peering-live-20260816T005124Z`

Credential values remain outside Git. The protected credential file is `/etc/wwcx/credentials/eternal-september.json`; accepted metadata is `root:wwcx-comms` mode `0640`.

## Provenance accounting rule

Imported local groups can contain more than one legitimate provenance class. In particular, `wwcx-bootstrap` adds a one-time group introduction.

Do not require total group article count to equal external-source ledger count. Validate by:

- `ingest_items.source_name`;
- unique `source_item_id`;
- target-group membership;
- stored `X-WWCX-*` provenance;
- duplicate count;
- explicitly understood local provenance classes.

## Private News Reader v2 — accepted live

The read-only News Reader is served by the existing control listener at:

`http://127.0.0.1:8100/news.html`

Accepted capabilities:

- newsgroup browsing;
- bounded search;
- article body/detail view;
- raw stored headers;
- source/provenance and cursor information;
- exact source filters including Eternal September, WW.CX Bootstrap, Edge1 Repository and native/local;
- 25/50/100 pagination with exact totals and previous/next offsets;
- threaded and flat-list views using stored `References` or `X-WWCX-Upstream-References` ancestry.

The exact validated reader blob set was reconciled to repository history through PR #341, merge commit `6a0397a7f39c07afa3a779c0578e06d165df41e8`. PR #337 is historical/superseded. Durable relay state was updated through PR #342, merge commit `1c115663fb23de82e51fcfd0520d91fa196261be`.

Acceptance record:

`docs/communications/edge1-comms-relay-news-reader-live-acceptance-20260817.md`

## Protected archive — sealed

Archive closeout:

`docs/archive/edge1-comms-relay-news-reader-closeout-20260817.md`

Final seal record:

`docs/archive/edge1-comms-relay-archive-seal-20260817.md`

Protected archive root:

`/var/lib/wwcx-deployment-evidence/comms-relay/archive-seal-20260817T023340Z`

Archive package manifest SHA-256:

`e218e3939ef823d2b36f7a413fb78fad836879bbffd958824254c421008eb3b8`

Final archive reconciliation:

```text
top_level_evidence_roots=16
retained_evidence_files=138
news_reader_v2_evidence_root=unavailable-not-created
unavailable_source_records=1
exact_duplicate_hash_groups=20
exact_duplicate_file_rows=73
historical_credential_file_exclusions=0
live_credential_content_exclusions=1
live_object_unavailable=0
errors=0
inventory_idempotence=PASS
ARCHIVE_SEAL_GATE=PASS
```

The News Reader v2 dedicated evidence source has terminal disposition `unavailable-not-created`: its accepted deployment did not create a dedicated protected evidence directory and later discovery found none. Do not retry discovery without new contrary evidence. Production acceptance remains preserved by branch/head/result and the dated acceptance/repository records.

The final inventory froze all 16 pre-existing top-level Communications Relay evidence directories and included `/var/lib/wwcx-comms/config-control` history. Two complete inventory passes were byte-for-byte identical. Exact duplicates were reported and retained rather than deleted.

The live config and SQLite database were hashed/metadata-recorded as restricted objects and were not copied into Git. Eternal September credential contents were explicitly excluded; only non-secret exclusion metadata was retained.

## Safety boundary

Still disabled or separately gated:

- public IRC/NNTP exposure;
- upstream posting;
- inbound NNTP feeds;
- server-to-server streaming;
- formal bidirectional peering;
- DNS or firewall changes for the relay;
- certificate changes for the relay;
- forwarding private `wwcx.*` articles upstream;
- deletion or pruning of retained evidence solely because the archive is sealed.
