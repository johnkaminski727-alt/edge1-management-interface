# Edge1 Communications Relay Private News Reader

## Purpose

The WW.CX News Reader is a private, read-only browser for articles already stored by the Edge1 Communications Relay. It provides a human-friendly way to inspect local NNTP newsgroups without exposing the NNTP listener publicly or enabling web posting.

## Security and scope

The News Reader is served by the existing loopback-only Communications Relay control listener. It does not add a new network listener and does not alter NNTP authentication, posting, peering, DNS, firewall, or certificate configuration.

The control API remains read-only. `POST`, `PUT`, `PATCH`, and `DELETE` requests return `405` with `read_only_control_api`.

Article bodies are returned only by the single-article detail endpoint. Group article listings return metadata, threading fields, and provenance only, keeping list responses bounded.

Credential values and credential-file contents are never exposed by the News Reader. Source configuration comes from the existing sanitized relay configuration.

## User interface

The existing Communications Relay operations page links to `news.html`.

The News Reader provides:

- total group, article, enabled-source, and current-match counts;
- newsgroup list with retention and article counts;
- source status, mapping, item count, cursor, and last update state;
- bounded per-group pagination with 25, 50, or 100 articles per page;
- previous/next controls with exact visible range and total-match reporting;
- bounded search by subject, author, local Message-ID, source name, or source item ID;
- exact source filtering, including `Native / local`, WW.CX Bootstrap, Edge1 Repository, and each Eternal September source;
- thread and flat-list views;
- thread grouping based on stored message-reference ancestry rather than subject guessing;
- article detail with body, stored headers, and provenance.

Thread mode works with both storage models already used by the relay:

- native WW.CX posts use the normal stored `References` value (`references_text`);
- imported Usenet articles use the preserved `X-WWCX-Upstream-References` header.

The first referenced Message-ID becomes the thread key and the last referenced Message-ID is exposed as the immediate thread parent. Thread indentation is bounded in the UI. Thread grouping is page-scoped: a conversation longer than the selected page size can continue on the next page.

## Read-only API

- `GET /api/comms/news/groups`
- `GET /api/comms/news/groups/<group>`
- `GET /api/comms/news/groups/<group>/articles?limit=50&offset=0&q=<search>&source=<source>`
- `GET /api/comms/news/articles/<article-id>`
- `GET /api/comms/news/sources`

Article-list pagination is bounded to a maximum of 100 rows per response. `offset` is non-negative and bounded by the control handler. The response includes:

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

For ingested articles the reader combines the existing `ingest_items` ledger with stored `X-WWCX-*` headers. The detail view can therefore show local and upstream identity without reading external credentials or contacting the upstream provider.

Typical Eternal September provenance includes:

- source name;
- source item ID;
- upstream server;
- upstream group;
- upstream article number;
- upstream Message-ID;
- local deterministic Message-ID;
- ingest timestamp.

## Validation

`tests/validate_comms_news_reader.py` exercises the control server against a temporary SQLite database containing an imported root article, an imported reply, and a native/local article. It verifies:

- group counts;
- offset pagination and previous/next metadata;
- list responses exclude article bodies;
- exact ingestion-source filtering;
- the special native/local source filter;
- combined search + source filtering;
- source counts;
- imported reply threading from `X-WWCX-Upstream-References`;
- root/parent/depth thread metadata;
- article detail body and provenance;
- source endpoint readability;
- web mutation attempts remain blocked with HTTP 405.

Production deployment must retain the existing loopback-only control, IRC, and NNTP listener posture and use the normal bounded service-readiness check after restart.
