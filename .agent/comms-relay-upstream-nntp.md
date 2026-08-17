# Edge1 Communications Relay Upstream NNTP State

Last reconciled: 2026-08-17

## Objective

Operate Edge1 as a controlled outbound-only NNTP reader that selectively mirrors explicitly allowlisted public Usenet groups into a separate local `usenet.*` namespace, while keeping the Communications Relay private-first and the HTTP control/News Reader surface read-only.

## Repository implementation state

Validated NNTP implementation floor:

`c7b4b2c9124e072abaa356f0645e10d449c38eea`

Implemented behavior includes:

- `nntp` ingestion source type;
- TLS-required upstream reader connections;
- one upstream group to one local group mapping per source;
- optional creation of only the explicitly configured local group;
- credential-file reference rather than credential values in relay configuration;
- bounded initial lookback, scan limit, run budget, article byte ceiling and retention;
- single-part `text/*` article acceptance;
- upstream Message-ID deduplication;
- deterministic local Message-ID;
- upstream author and `X-WWCX-Upstream-*` provenance preservation;
- article-number cursor with bounded reset/rewrite recovery;
- private read-only News Reader for stored relay articles.

News Reader repository reconciliation:

- PR #341 merged the exact validated nine-file blob set;
- merge commit: `6a0397a7f39c07afa3a779c0578e06d165df41e8`;
- PR #337 closed as superseded development history.

Durable state reconciliation:

- PR #342;
- merge commit: `1c115663fb23de82e51fcfd0520d91fa196261be`.

Archive/documentation reconciliation:

- PR #344 comprehensive documentation/archive preparation;
- PR #345 closeout merge-point record;
- PR #346 final protected archive seal, merge commit `17c3e665bc218862c3b7eb3b28cae856ed4209e7`.

## Accepted upstream service

Reader endpoint:

- host: `news.eternal-september.org`;
- port: `563`;
- TLS: required.

The separate feeder/peering service is not part of this production state. Reader pulling is not formal peering.

## Live source 1 — `eternal.comp.lang.python`

- upstream group: `comp.lang.python`;
- local target: `usenet.comp.lang.python`;
- credential file: `/etc/wwcx/credentials/eternal-september.json`;
- accepted credential metadata: `root:wwcx-comms 0640`;
- retention: 3650 days;
- maximum article size: 262144 bytes;
- initial items: 8;
- scan limit: 10;
- accepted external items: 8;
- accepted bootstrap introduction: 1 (`usenet.comp.lang.python:v1`);
- duplicate external source IDs: 0.

Evidence root:

`/var/lib/wwcx-deployment-evidence/comms-relay/eternal-september-live-20260815T233435Z`

Acceptance record:

`docs/communications/edge1-comms-relay-upstream-nntp-live-acceptance-20260815.md`

## Live source 2 — `eternal.news.admin.peering`

- upstream group: `news.admin.peering`;
- local target: `usenet.news.admin.peering`;
- same protected credential file;
- retention: 3650 days;
- maximum article size: 262144 bytes;
- initial items: 8;
- scan limit: 10;
- accepted external items: 8;
- accepted bootstrap introduction: 1 (`usenet.news.admin.peering:v1`);
- cursor present and accepted;
- duplicate external source IDs: 0;
- wrong-group/orphan/bad-provenance/unexpected-provenance counts: 0;
- ingestion errors since activation: 0 at acceptance.

Candidate/dry-run evidence:

`/var/lib/wwcx-deployment-evidence/comms-relay/eternal-news-admin-peering-prep-20260816T001246Z`

Guarded recovery attempt:

`/var/lib/wwcx-deployment-evidence/comms-relay/eternal-news-admin-peering-live-20260816T002007Z`

Accepted live evidence:

`/var/lib/wwcx-deployment-evidence/comms-relay/eternal-news-admin-peering-live-20260816T005124Z`

Acceptance record:

`docs/communications/edge1-comms-relay-upstream-nntp-second-source-live-acceptance-20260816.md`

## Accepted automatic source order

1. `wwcx-bootstrap`;
2. `eternal.comp.lang.python`;
3. `eternal.news.admin.peering`;
4. `edge1-repository`.

The order explains why a newly created imported group may receive its one-time bootstrap introduction on the next ingestion pass.

## Provenance accounting rule

Do not require an imported local group's total article count to equal the external source ledger count.

Validate:

- exact `source_name`;
- unique `source_item_id`;
- target group;
- stored WW.CX/upstream provenance;
- cursor;
- duplicate/orphan/wrong-group/unexpected-provenance counts;
- legitimate additional source classes such as `wwcx-bootstrap`.

## Private News Reader v2

Accepted production checkout:

- branch: `deploy/private-nntp-news-reader-v2-20260817`;
- head: `974c7141e18deac92671f81fb1bd3c3ed02a6c68`;
- result: `NEWS_READER_V2_DEPLOYMENT=PASS`.

Reader URL:

`http://127.0.0.1:8100/news.html`

Accepted capabilities include search, exact source filters, 25/50/100 pagination, article detail/provenance, raw stored headers, source cursor/item state, and threaded/flat views based on stored reference ancestry.

Mutation attempts remain blocked with HTTP 405 `read_only_control_api`.

Acceptance record:

`docs/communications/edge1-comms-relay-news-reader-live-acceptance-20260817.md`

## Checkout discipline

Do not assume live Edge1 equals current remote `main`.

The News Reader was validated on an isolated production deployment branch. Do not switch or pull the production relay to current `main` merely to reconcile history.

## Archive state

Archive closeout:

`docs/archive/edge1-comms-relay-news-reader-closeout-20260817.md`

Final seal record:

`docs/archive/edge1-comms-relay-archive-seal-20260817.md`

State: **SEALED**.

Protected archive root:

`/var/lib/wwcx-deployment-evidence/comms-relay/archive-seal-20260817T023340Z`

Archive package manifest SHA-256:

`e218e3939ef823d2b36f7a413fb78fad836879bbffd958824254c421008eb3b8`

Final archive validation:

```text
ARCHIVE_SEAL_GATE=PASS
inventory_idempotence=PASS
top_level_evidence_roots=16
retained_evidence_files=138
news_reader_v2_evidence_root=unavailable-not-created
unavailable_source_records=1
exact_duplicate_hash_groups=20
exact_duplicate_file_rows=73
live_object_unavailable=0
errors=0
```

The News Reader v2 dedicated evidence source has terminal disposition `unavailable-not-created`; its accepted deployment did not create a dedicated protected evidence directory and later pathname/marker discovery found none. Do not invent or keep searching for a path absent new contrary evidence.

Credential contents were explicitly excluded from the archive payload. Exact duplicate records were reported and retained. Live config and SQLite were hash/metadata-recorded without being committed. Two complete inventory passes were byte-for-byte identical.

## Safety boundaries

Still disabled or separately gated:

- upstream posting;
- inbound NNTP feeds;
- `IHAVE`, `CHECK`, `TAKETHIS` or streaming federation;
- formal bidirectional peering;
- DNS/firewall/certificate changes for the relay;
- public Edge1 IRC/NNTP exposure;
- forwarding private `wwcx.*` articles upstream;
- deleting retained evidence merely because the archive is sealed.
