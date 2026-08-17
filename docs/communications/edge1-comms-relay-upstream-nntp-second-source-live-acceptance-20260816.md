# Edge1 Communications Relay — Second Upstream NNTP Source Live Acceptance

Date: 2026-08-16  
Classification: sanitized operational acceptance record  
Host: `edge1.ww.cx`  
Service: `edge1-comms-relay.service`

## Scope

This record preserves the accepted activation of exactly one additional outbound-only Eternal September NNTP reader mapping:

- source: `eternal.news.admin.peering`;
- upstream: `news.eternal-september.org:563`;
- upstream group: `news.admin.peering`;
- local group: `usenet.news.admin.peering`;
- TLS: required;
- credential file: existing protected `/etc/wwcx/credentials/eternal-september.json`;
- retention: 3650 days;
- maximum article size: 262144 bytes;
- initial lookback: 8 items;
- scan limit: 10 items.

No credential values are contained in this record.

## Repository and checkout discipline

The activation was a configuration-only production change. The relay implementation floor was already merged and validated. The attended operation froze the local Edge1 checkout rather than chasing unrelated movement on remote `main`.

The production checkout used for the Communications Relay remained subject to the established rule: unrelated repository work must not be pulled into the relay merely to reconcile documentation history.

## Pre-activation validation

Before apply:

- the existing relay was enabled, active and healthy;
- the three relay listeners remained loopback-only;
- live configuration metadata remained `root:wwcx-comms` mode `0640`;
- credential-file metadata remained `root:wwcx-comms` mode `0640`;
- the candidate added exactly the reviewed `news.admin.peering` mapping;
- candidate validation and config diff passed;
- a fresh config backup and SQLite backup were captured;
- SQLite quick-check passed;
- an attended real TLS dry run returned 8 bounded candidate articles for the intended local group;
- the dry run did not create the group, articles, cursor, or ingest-state mutation.

Candidate-preparation evidence root:

`/var/lib/wwcx-deployment-evidence/comms-relay/eternal-news-admin-peering-prep-20260816T001246Z`

## Recovery rehearsal during activation

An early activation attempt encountered a service-readiness race: systemd reported the `Type=simple` relay process active before the loopback HTTP control listener had bound. The guarded workflow restored the prior configuration and restarted the relay. Follow-up verification proved:

- original live configuration hash restored;
- config and credential metadata preserved;
- health returned `ok` after bounded readiness;
- all expected listeners remained loopback-only;
- no new source group, items, cursor, bootstrap introduction, or candidate-era database mutation occurred.

This was a readiness-timing issue, not a candidate-content failure. The final activation used bounded readiness instead of treating immediate `systemctl is-active` as application readiness.

## Accepted live result

Final acceptance evidence root:

`/var/lib/wwcx-deployment-evidence/comms-relay/eternal-news-admin-peering-live-20260816T005124Z`

Accepted provenance state:

- 8 articles from `eternal.news.admin.peering`;
- 1 one-time `wwcx-bootstrap` introduction with source item ID `usenet.news.admin.peering:v1`;
- cursor present and accepted;
- duplicate external source IDs: 0;
- wrong-group count: 0;
- orphan count: 0;
- bad-provenance count: 0;
- unexpected-provenance count: 0;
- ingestion errors since activation: 0 at acceptance.

The earlier accepted `eternal.comp.lang.python` source remained intact.

## Listener and safety posture

The relay remained private-first with listeners on:

- IRC: `127.0.0.1:16667`;
- NNTP: `127.0.0.1:1119`;
- control/API: `127.0.0.1:8100`.

No DNS, firewall, certificate, public-listener, posting, inbound-feed, streaming, formal-peering, or private `wwcx.*` forwarding change was made.

## Provenance accounting rule

Do not compare total articles in an imported group directly to the external-source ledger count. The accepted group also contains the legitimate one-time `wwcx-bootstrap` introduction. Validate by `ingest_items.source_name`, source-item identity, target-group membership, stored provenance headers, and duplicate counts.

## Archive treatment

This record is sanitized and suitable for repository retention. Preserve the protected evidence roots on Edge1. Do not add the Eternal September credential file, credential values, raw authentication material, or the live SQLite database to Git.