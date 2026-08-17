# Edge1 Communications Relay: Selective Upstream NNTP Pull

Status: two allowlisted sources accepted live  
Last reconciled: 2026-08-17

## Purpose

The private WW.CX Edge1 Communications Relay supports controlled outbound-only NNTP reader sources. Each source copies one explicitly allowlisted public Usenet group into a clearly separated local `usenet.*` namespace without enabling NNTP peering, inbound feeds, public listeners, or federation.

Eternal September is the current upstream reader provider.

## Upstream service boundary

The implementation uses:

- reader host: `news.eternal-september.org`;
- TLS reader port: `563`;
- authenticated reader mode;
- normal TLS certificate and hostname verification.

The separate Eternal September feeder/peering service is not used. Successful reader pulling must never be described as formal NNTP peering.

## Accepted live mappings

### `eternal.comp.lang.python`

- upstream group: `comp.lang.python`;
- local group: `usenet.comp.lang.python`;
- retention: 3650 days;
- max article bytes: 262144;
- initial items: 8;
- scan limit: 10;
- accepted external items: 8;
- accepted bootstrap introduction: 1;
- duplicate external source IDs: 0.

Acceptance evidence:

`/var/lib/wwcx-deployment-evidence/comms-relay/eternal-september-live-20260815T233435Z`

### `eternal.news.admin.peering`

- upstream group: `news.admin.peering`;
- local group: `usenet.news.admin.peering`;
- retention: 3650 days;
- max article bytes: 262144;
- initial items: 8;
- scan limit: 10;
- accepted external items: 8;
- accepted bootstrap introduction: 1;
- duplicate external source IDs: 0;
- wrong-group/orphan/bad-provenance/unexpected-provenance counts: 0 at acceptance;
- ingestion errors since activation: 0 at acceptance.

Candidate/dry-run evidence:

`/var/lib/wwcx-deployment-evidence/comms-relay/eternal-news-admin-peering-prep-20260816T001246Z`

Accepted live evidence:

`/var/lib/wwcx-deployment-evidence/comms-relay/eternal-news-admin-peering-live-20260816T005124Z`

The guarded failed/recovery attempt around `20260816T002007Z` is retained as operational history because it demonstrated the service-readiness race and successful config rollback without candidate-era database mutation.

## Security boundary

The upstream reader implementation is outbound-only and TLS-required. It does not:

- listen on a new port;
- change DNS or firewall policy;
- accept incoming NNTP feeds;
- send WW.CX articles upstream;
- enable `IHAVE`, `CHECK`, `TAKETHIS`, streaming feeds, or server-to-server peering;
- store account credential values in the repository;
- automatically enumerate and mirror every upstream group.

Every source maps exactly one explicitly allowlisted upstream group to one local group. This gives each mapping separate enable/disable state, cursor, retention, scan budget, article-size ceiling and audit/provenance identity.

## Namespace policy

External groups belong beneath `usenet.*`, never directly inside the native `wwcx.*` hierarchy.

Accepted examples:

- `comp.lang.python` -> `usenet.comp.lang.python`;
- `news.admin.peering` -> `usenet.news.admin.peering`.

Future possible mappings such as `news.software.nntp`, `news.software.readers`, or `comp.protocols.time.ntp` remain unapproved until separately allowlisted and validated.

## Article identity and provenance

For an imported article:

- upstream Message-ID is the ingestion source-item ID and deduplication identity;
- WW.CX generates a deterministic local Message-ID rather than reusing the upstream identity;
- upstream author is preserved as the displayed author;
- upstream group, server, Message-ID, article number, content type, date and References are preserved in `X-WWCX-Upstream-*` headers when available;
- `X-WWCX-Automated`, `X-WWCX-Source`, and `X-WWCX-Source-ID` remain present through the common ingestion ledger.

The local deterministic Message-ID prevents imported content from impersonating a native WW.CX article while preserving exact upstream traceability.

## Content controls

The adapter accepts only bounded single-part `text/*` articles and skips/rejects:

- multipart MIME articles;
- non-text content types;
- articles without a syntactically valid upstream Message-ID;
- malformed header values;
- articles beyond the configured byte ceiling;
- unavailable or expired article numbers.

The global ingestion `max_items_per_run` limit still applies in addition to each source's `initial_items` and `scan_limit` bounds.

## Cursor and rewrite behavior

Each source stores its last scanned upstream article number independently in `ingest_state`. Normal runs scan newer article numbers. If the upstream high-water mark moves behind the stored cursor, the source treats that as a bounded reset/rewrite condition rather than blindly replaying history.

Deduplication uses upstream Message-ID, so upstream renumbering alone does not duplicate an article.

## Credential handling

Credentials are not permitted in the relay JSON. The accepted sources reference:

`/etc/wwcx/credentials/eternal-september.json`

Accepted metadata:

`root:wwcx-comms 0640`

The credential file contents must never be committed, pasted into chat/tickets, printed during archival work, or copied into deployment evidence. Sanitized configuration exposes only safe source configuration state.

## Provenance-aware acceptance

Do not require `local_group_article_count == external_source_item_count`.

`wwcx-bootstrap` can legitimately add a one-time introduction to a newly created imported group. Acceptance must instead reconcile:

- external source-item count;
- unique upstream Message-IDs/source-item IDs;
- group membership;
- cursor state;
- stored provenance headers;
- bootstrap introduction count;
- any other explicitly understood source class;
- duplicate/orphan/unexpected-provenance counts.

## Service readiness lesson

The relay systemd unit uses `Type=simple`. After restart, `systemctl is-active` can become true before the HTTP control listener has bound. Use bounded `/healthz` and listener readiness checks rather than an immediate one-shot curl.

The second-source activation proved the rollback path and then succeeded using bounded readiness.

## Adding another source

Add only one mapping at a time:

1. freeze a clean tested local checkout and record it;
2. verify the NNTP implementation floor is present;
3. back up live config and SQLite;
4. create one candidate source mapping;
5. validate and diff the candidate;
6. run an attended real-TLS dry run;
7. prove dry-run non-mutation;
8. stage/apply and restart only the relay;
9. wait for bounded health/listener readiness;
10. run attended ingestion as needed;
11. validate external provenance, duplicate count, cursor and bootstrap introduction;
12. preserve sanitized evidence and update the acceptance/state records.

Do not chase unrelated remote `main` movement during a config-only operation.

## Accepted records

- first source: `edge1-comms-relay-upstream-nntp-live-acceptance-20260815.md`;
- second source: `edge1-comms-relay-upstream-nntp-second-source-live-acceptance-20260816.md`;
- validation rules: `edge1-comms-relay-upstream-nntp-validation.md`;
- current state: `../../.agent/comms-relay-upstream-nntp.md`.

## Archive status

Archive preparation is tracked in `../archive/edge1-comms-relay-news-reader-closeout-20260817.md`. The documentation is ready; the archive is not sealed until the protected evidence SHA-256 inventory and exact News Reader evidence path are reconciled.
