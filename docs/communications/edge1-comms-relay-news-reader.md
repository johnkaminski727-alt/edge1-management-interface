# Edge1 Communications Relay Private News Reader

Status: v2 accepted live  
Last reconciled: 2026-08-17

## Purpose

The WW.CX News Reader is a private, read-only browser for articles already stored by the Edge1 Communications Relay. It provides a human-friendly way to inspect local NNTP newsgroups without exposing the NNTP listener publicly or enabling web posting.

The reader contacts the local Communications Relay control API/database only; browsing does not contact Eternal September or any other upstream source.

## Accepted production state

Live deployment branch:

`deploy/private-nntp-news-reader-v2-20260817`

Live deployment head:

`974c7141e18deac92671f81fb1bd3c3ed02a6c68`

Acceptance result:

`NEWS_READER_V2_DEPLOYMENT=PASS`

Live URL on Edge1 loopback:

`http://127.0.0.1:8100/news.html`

The exact validated reader blob set was integrated into repository history by PR #341, merge commit `6a0397a7f39c07afa3a779c0578e06d165df41e8`. PR #337 is retained only as superseded development history. Durable Communications Relay state was updated through PR #342, merge commit `1c115663fb23de82e51fcfd0520d91fa196261be`.

Repository reconciliation does not authorize moving the live Edge1 checkout to current remote `main`; unrelated time-authority work is present there and requires separate production review.

## Security and scope

The News Reader is served by the existing loopback-only Communications Relay control listener. It does not:

- add a network listener;
- alter NNTP authentication or posting policy;
- expose local NNTP publicly;
- enable inbound feeds or formal peering;
- change DNS, firewall or certificates;
- read or expose upstream credential values;
- modify relay articles, groups, source state or cursors.

The control API remains read-only. `POST`, `PUT`, `PATCH`, and `DELETE` requests return HTTP 405 with `read_only_control_api`.

Article bodies are returned only by the single-article detail endpoint. Group article listings return bounded metadata, threading fields and provenance only.

## User interface

The Communications Relay operations page links to `news.html`.

The News Reader provides:

- total group, article, enabled-source and current-match counts;
- newsgroup list with retention and article counts;
- source status, mapping, item count, cursor and last-update state;
- bounded per-group pagination with 25, 50 or 100 articles per page;
- previous/next controls with exact visible range and total-match reporting;
- bounded search by subject, author, local Message-ID, source name or source item ID;
- exact source filtering, including Native/local, WW.CX Bootstrap, Edge1 Repository, `eternal.comp.lang.python`, and `eternal.news.admin.peering`;
- threaded and flat-list views;
- article detail with body, stored headers and provenance.

## Thread model

Thread mode works with both storage models used by the relay:

- native WW.CX posts use stored `References` (`references_text`);
- imported Usenet articles use preserved `X-WWCX-Upstream-References` when native references are absent.

The first referenced Message-ID becomes the thread key and the last referenced Message-ID is exposed as the immediate parent. Thread indentation is bounded in the UI.

Thread grouping is page-scoped: a conversation longer than the selected page size can continue on another page. The UI does not invent a thread relationship from matching subject text.

## Read-only API

- `GET /api/comms/news/groups`
- `GET /api/comms/news/groups/<group>`
- `GET /api/comms/news/groups/<group>/articles?limit=50&offset=0&q=<search>&source=<source>`
- `GET /api/comms/news/articles/<article-id>`
- `GET /api/comms/news/sources`

Article-list pagination is bounded to a maximum of 100 rows per response. `offset` is non-negative and bounded by the control handler.

List responses include:

- `articles`;
- `pagination.total`;
- `pagination.limit`;
- `pagination.offset`;
- `pagination.returned`;
- `pagination.previous_offset` / `next_offset`;
- `source_counts` for the current group/search before source filtering;
- `thread_key`, `thread_parent`, `thread_depth`, and `thread_references` on each article summary.

The special source filter value `native` selects articles with no `ingest_items` provenance row. Other source filters are exact `source_name` matches and are parameterized in SQLite.

## Provenance

For ingested articles the reader combines the existing `ingest_items` ledger with stored `X-WWCX-*` headers. It can therefore show local and upstream identity without reading external credentials or contacting the upstream provider.

Typical Eternal September provenance includes:

- source name;
- source item ID;
- upstream server;
- upstream group;
- upstream article number;
- upstream Message-ID;
- local deterministic Message-ID;
- ingest timestamp.

Group totals are not assumed to equal an external-source count because `wwcx-bootstrap` can add a legitimate one-time introduction to the same group.

## Validation

`tests/validate_comms_news_reader.py` exercises the control server against a temporary SQLite database containing an imported root article, imported reply and native/local article. It verifies:

- group counts;
- offset pagination and previous/next metadata;
- list responses exclude article bodies;
- exact ingestion-source filtering;
- native/local source filtering;
- combined search + source filtering;
- source counts;
- imported reply threading from `X-WWCX-Upstream-References`;
- root/parent/depth thread metadata;
- article detail body and provenance;
- source endpoint readability;
- web mutation attempts remain blocked with HTTP 405.

Live v2 acceptance additionally passed Communications Relay production-readiness, ingestion regression, upstream NNTP TLS, config-control metadata, JavaScript syntax, bounded service readiness, loopback listener verification, live source-filter checks and final relay health.

Accepted listener posture remained:

- `127.0.0.1:1119`;
- `127.0.0.1:16667`;
- `127.0.0.1:8100`.

## Acceptance and archive records

Live acceptance:

`edge1-comms-relay-news-reader-live-acceptance-20260817.md`

Archive closeout:

`../archive/edge1-comms-relay-news-reader-closeout-20260817.md`

Archive state is **prepared, not sealed** until the exact host-side News Reader evidence directory and SHA-256 inventory are reconciled.