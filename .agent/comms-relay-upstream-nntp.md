# Edge1 Communications Relay Upstream NNTP State

Date: 2026-08-17

## Objective

Operate Edge1 as a controlled outbound-only NNTP reader that selectively mirrors explicitly allowlisted public Usenet groups into a separate local `usenet.*` namespace, while keeping the Communications Relay private-first and read-only from its web control surface.

## Reference upstream

Eternal September is the initial reference provider.

Verified public technical state used by this implementation:

- reader hostname: `news.eternal-september.org`;
- TLS reader port: `563`;
- separate peering/transit hostname: `feeder.eternal-september.org`;
- formal peering/transit is not part of the current phase.

## Repository implementation state

The selective outbound NNTP implementation is merged. The validated implementation floor is:

`c7b4b2c9124e072abaa356f0645e10d449c38eea`

Implemented behavior includes:

- `nntp` ingestion source type;
- TLS required for upstream reader connections;
- one upstream group to one local group mapping per source;
- optional automatic creation of only the explicitly configured local group;
- credential-file reference rather than credential values in relay configuration;
- sanitized config exposes only whether a credential file is configured;
- bounded initial lookback, scan limit, per-run budget, article byte ceiling, and retention;
- single-part `text/*` article acceptance only;
- upstream Message-ID deduplication;
- deterministic WW.CX local Message-ID;
- upstream author and provenance headers preserved;
- article-number cursor with bounded reset/rewrite recovery;
- scripted no-network protocol validation for AUTHINFO/GROUP/ARTICLE parsing;
- private read-only News Reader for stored relay articles.

The private News Reader repository reconciliation was merged to `main` by PR #341 at merge commit:

`6a0397a7f39c07afa3a779c0578e06d165df41e8`

PR #337 is retained only as superseded development history.

## Live upstream state

Two Eternal September sources are accepted live on Edge1.

### 1. comp.lang.python

- source name: `eternal.comp.lang.python`;
- upstream: `news.eternal-september.org:563`;
- upstream group: `comp.lang.python`;
- local target: `usenet.comp.lang.python`;
- TLS required;
- credential file: `/etc/wwcx/credentials/eternal-september.json`;
- credential metadata observed as `root:wwcx-comms` mode `0640`;
- retention: 3650 days;
- maximum article size: 262144 bytes;
- initial window: 8;
- scan ceiling: 10;
- scheduled through the existing 900-second relay ingestion cycle.

Acceptance evidence root:

`/var/lib/wwcx-deployment-evidence/comms-relay/eternal-september-live-20260815T233435Z`

Accepted data state:

- 8 articles from `eternal.comp.lang.python`;
- 1 one-time `wwcx-bootstrap` introduction with source item ID `usenet.comp.lang.python:v1`;
- duplicate Eternal September source IDs: 0.

### 2. news.admin.peering

- source name: `eternal.news.admin.peering`;
- upstream: `news.eternal-september.org:563`;
- upstream group: `news.admin.peering`;
- local target: `usenet.news.admin.peering`;
- TLS required;
- same protected Eternal September credential file;
- retention: 3650 days;
- maximum article size: 262144 bytes;
- initial window: 8;
- scan ceiling: 10;
- scheduled through the existing 900-second relay ingestion cycle.

Acceptance evidence root:

`/var/lib/wwcx-deployment-evidence/comms-relay/eternal-news-admin-peering-live-20260816T005124Z`

Accepted data state:

- 8 articles from `eternal.news.admin.peering`;
- 1 one-time `wwcx-bootstrap` introduction with source item ID `usenet.news.admin.peering:v1`;
- cursor present and accepted at activation;
- duplicate Eternal September source IDs: 0;
- wrong-group, orphan, bad-provenance, and unexpected-provenance counts: 0;
- ingestion errors since activation: 0 at acceptance.

The accepted automatic source order is:

1. `wwcx-bootstrap`;
2. `eternal.comp.lang.python`;
3. `eternal.news.admin.peering`;
4. `edge1-repository`.

Validation must remain provenance-aware. Do not require a local group's total article count to equal its external source ledger count when another approved source, such as `wwcx-bootstrap`, also posts to the group.

## Private News Reader live state

News Reader v2 is accepted live on Edge1.

Live deployment branch:

`deploy/private-nntp-news-reader-v2-20260817`

Live deployment head:

`974c7141e18deac92671f81fb1bd3c3ed02a6c68`

Acceptance result:

`NEWS_READER_V2_DEPLOYMENT=PASS`

The reader is served by the existing loopback-only control listener at:

`http://127.0.0.1:8100/news.html`

It provides:

- newsgroup browsing;
- bounded article search;
- article body/detail and raw stored headers;
- source/provenance and cursor information;
- exact source filters including Eternal September, WW.CX Bootstrap, Edge1 Repository, and native/local articles;
- 25 / 50 / 100 article pagination with previous/next offsets and exact totals;
- threaded and flat-list views using actual stored `References` or `X-WWCX-Upstream-References` ancestry.

Live validation passed for:

- News Reader threaded pagination/source-filter tests;
- Communications Relay production-readiness, ingestion, upstream NNTP TLS, and config-control metadata tests;
- JavaScript syntax;
- bounded service readiness;
- loopback-only listeners on `127.0.0.1:1119`, `127.0.0.1:16667`, and `127.0.0.1:8100`;
- read-only mutation enforcement (`405 read_only_control_api`);
- preservation of both accepted Eternal September source ledgers;
- final relay health.

## Checkout discipline

Do not assume the live Edge1 repository checkout equals current remote `main`.

The News Reader was validated on an isolated local deployment branch. Remote `main` subsequently also contains separate time-authority work. Do not switch/pull Edge1 to current `main` merely to reconcile repository history; unrelated production work must be reviewed and deployed under its own acceptance process.

## Safety boundaries

The live upstream sources are outbound reader-pull only.

Still disabled or separately gated:

- upstream posting;
- inbound NNTP feeds;
- server-to-server streaming;
- formal bidirectional peering;
- DNS or firewall changes for the relay;
- public Edge1 IRC/NNTP exposure;
- forwarding private WW.CX articles upstream.

The News Reader remains private and read-only. Additional public groups must be added as separate explicit allowlisted mappings and validated incrementally.
