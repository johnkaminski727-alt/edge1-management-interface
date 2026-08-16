# Edge1 Communications Relay Private News Reader

## Purpose

The WW.CX News Reader is a private, read-only browser for articles already stored by the Edge1 Communications Relay. It provides a human-friendly way to inspect local NNTP newsgroups without exposing the NNTP listener publicly or enabling web posting.

## Security and scope

The News Reader is served by the existing loopback-only Communications Relay control listener. It does not add a new network listener and does not alter NNTP authentication, posting, peering, DNS, firewall, or certificate configuration.

The control API remains read-only. `POST`, `PUT`, `PATCH`, and `DELETE` requests return `405` with `read_only_control_api`.

Article bodies are returned only by the single-article detail endpoint. Group article listings return metadata and provenance only, keeping list responses bounded.

Credential values and credential-file contents are never exposed by the News Reader. Source configuration comes from the existing sanitized relay configuration.

## User interface

The existing Communications Relay operations page links to `news.html`.

The News Reader provides:

- total group, article, and enabled-source counts;
- newsgroup list with retention and article counts;
- source status, mapping, item count, cursor, and last update state;
- per-group article lists ordered newest first;
- bounded search by subject, author, local Message-ID, source name, or source item ID;
- article detail with body, stored headers, and provenance;
- source-friendly labels for Eternal September, WW.CX Bootstrap, Edge1 Repository, and native articles.

## Read-only API

- `GET /api/comms/news/groups`
- `GET /api/comms/news/groups/<group>`
- `GET /api/comms/news/groups/<group>/articles?limit=100&q=<search>`
- `GET /api/comms/news/articles/<article-id>`
- `GET /api/comms/news/sources`

The article list limit is bounded to a maximum of 250 rows.

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

`tests/validate_comms_news_reader.py` exercises the control server against a temporary SQLite database and verifies:

- group counts;
- bounded article search;
- list responses exclude article bodies;
- article detail returns body and provenance;
- source endpoint is readable;
- web mutation attempts remain blocked with HTTP 405.

Production deployment must retain the existing loopback-only control, IRC, and NNTP listener posture and use the normal bounded service-readiness check after restart.
