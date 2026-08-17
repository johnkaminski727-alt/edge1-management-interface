# Edge1 Communications Relay — Private News Reader v2 Live Acceptance

Date: 2026-08-17  
Classification: sanitized operational acceptance record  
Host: `edge1.ww.cx`  
Service: `edge1-comms-relay.service`

## Scope

This record preserves the accepted production state of the private WW.CX News Reader v2. The reader is a read-only browser over articles already stored by the Edge1 Communications Relay. It does not create a new listener, expose NNTP publicly, enable web posting, or contact the upstream provider while browsing.

Live deployment branch:

`deploy/private-nntp-news-reader-v2-20260817`

Live deployment head:

`974c7141e18deac92671f81fb1bd3c3ed02a6c68`

Acceptance result:

`NEWS_READER_V2_DEPLOYMENT=PASS`

## Repository reconciliation

The exact nine-file News Reader blob set validated live was integrated onto the then-current repository `main` by PR #341 in one clean commit with no unrelated paths. PR #337 is retained only as superseded development history.

PR #341 merge commit:

`6a0397a7f39c07afa3a779c0578e06d165df41e8`

Durable Communications Relay state was then updated by PR #342.

PR #342 merge commit:

`1c115663fb23de82e51fcfd0520d91fa196261be`

Repository reconciliation does not authorize moving the live Edge1 checkout to remote `main`; unrelated time-authority work is also present there and requires its own production review.

## Accepted reader behavior

The reader is served by the existing loopback control listener:

`http://127.0.0.1:8100/news.html`

Accepted capabilities:

- newsgroup browsing;
- article body/detail view;
- raw stored header view;
- source and provenance display;
- source cursor/item-state display;
- bounded search by subject, author, local Message-ID, source name, or source item ID;
- exact source filtering for Eternal September sources, WW.CX Bootstrap, Edge1 Repository, and native/local articles;
- 25, 50, or 100 article pagination with exact totals and previous/next offsets;
- threaded and flat-list views;
- thread ancestry derived from stored `References` or `X-WWCX-Upstream-References`, not subject guessing.

Article-list responses remain bounded and do not include bodies. Article bodies are returned only by the single-article detail endpoint.

## Read-only API

Accepted endpoints include:

- `GET /api/comms/news/groups`;
- `GET /api/comms/news/groups/<group>`;
- `GET /api/comms/news/groups/<group>/articles`;
- `GET /api/comms/news/articles/<article-id>`;
- `GET /api/comms/news/sources`.

Mutation attempts remain blocked with HTTP 405 and `read_only_control_api`.

## Live validation

The accepted deployment passed:

- expanded News Reader threaded pagination and source-filter validation;
- Communications Relay production-readiness validation;
- controlled-ingestion regression validation;
- upstream NNTP TLS validation;
- config-control metadata validation;
- JavaScript syntax validation;
- bounded service restart/readiness verification;
- exact source-filter checks against live Eternal September and bootstrap data;
- loopback listener verification;
- final relay health verification.

Expected loopback listeners remained:

- `127.0.0.1:1119` — NNTP;
- `127.0.0.1:16667` — IRC;
- `127.0.0.1:8100` — control/API/News Reader.

Both accepted Eternal September source ledgers remained intact and duplicate external source IDs remained zero at acceptance.

## Security boundary

The News Reader did not change:

- DNS;
- firewall policy;
- certificates;
- authentication policy;
- public network exposure;
- upstream posting;
- inbound feeds;
- formal peering;
- private `wwcx.*` forwarding;
- database schema.

Credential-file contents are not exposed by the reader or retained in this record.

## Archive treatment

This record is sanitized and suitable for repository retention. The exact protected host-side News Reader deployment-evidence directory was not re-read during repository closeout and must be reconciled from Edge1 before the archive is sealed. Preserve the accepted deployment branch/head, service logs needed for acceptance, and the existing Communications Relay evidence roots; do not copy credentials or raw account-authentication material into the repository archive.