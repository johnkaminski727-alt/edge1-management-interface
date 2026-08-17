# Edge1 Communications Relay Documentation

Last reconciled: 2026-08-17

This directory contains the design, operations, validation and acceptance records for the WW.CX Edge1 Communications Relay, selective outbound NNTP ingestion, the private News Reader, and the private AI read-only communications integration.

## Current living documentation

Read these first for the current design and operating model:

1. `edge1-comms-relay-architecture.md` — current relay architecture and security boundary.
2. `edge1-comms-relay-ingestion.md` — automatic ingestion model and accepted source types.
3. `edge1-comms-relay-upstream-nntp.md` — selective outbound Eternal September reader integration.
4. `edge1-comms-relay-upstream-nntp-validation.md` — repository/live validation and provenance-accounting rules.
5. `edge1-comms-relay-news-reader.md` — private read-only News Reader behavior and API.
6. `../handoff/edge1-comms-relay-runbook.md` — operator runbook, readiness, rollback and archive handling.
7. `../../.agent/comms-relay.md` — concise current relay state.
8. `../../.agent/comms-relay-upstream-nntp.md` — current upstream NNTP and News Reader state.
9. `edge1-private-ai-chat-communications-permissions-and-regression-contract.md` — Private AI tool/scope distinction, consent boundary and source-controlled regression contract.

The Private AI contract is validated by `../../tests/validate_private_ai_gateway_contract.py`. The dependency-free suite exercises positive and negative fixtures; on Edge1 the same validator can inspect `/opt/bigbird-ai-gateway/app` statically with `--gateway-root` without importing the service or contacting the Relay.

## Accepted production state

The accepted private service remains loopback-only:

- IRC: `127.0.0.1:16667`;
- NNTP: `127.0.0.1:1119`;
- control/API/News Reader: `127.0.0.1:8100`.

Accepted outbound Eternal September mappings:

- `comp.lang.python` -> `usenet.comp.lang.python` as source `eternal.comp.lang.python`;
- `news.admin.peering` -> `usenet.news.admin.peering` as source `eternal.news.admin.peering`.

The private News Reader v2 is accepted live from deployment branch `deploy/private-nntp-news-reader-v2-20260817` at head `974c7141e18deac92671f81fb1bd3c3ed02a6c68` with result `NEWS_READER_V2_DEPLOYMENT=PASS`.

Repository integration of the exact validated reader blobs was merged through PR #341 as `6a0397a7f39c07afa3a779c0578e06d165df41e8`. Durable state was updated through PR #342 as `1c115663fb23de82e51fcfd0520d91fa196261be`.

Do not infer that the live Edge1 checkout should be moved to current remote `main`; unrelated production work is present there and must be deployed independently.

## Historical acceptance records

These dated records are immutable operational history. They should not be rewritten merely to match later state:

- `edge1-comms-relay-live-acceptance-20260815.md` — initial relay live acceptance;
- `edge1-comms-relay-ingestion-live-acceptance-20260815.md` — local automatic ingestion acceptance;
- `edge1-comms-relay-upstream-nntp-live-acceptance-20260815.md` — first Eternal September source acceptance;
- `edge1-comms-relay-upstream-nntp-second-source-live-acceptance-20260816.md` — second Eternal September source acceptance;
- `edge1-comms-relay-news-reader-live-acceptance-20260817.md` — News Reader v2 acceptance;
- `edge1-private-ai-chat-comms-rag-live-acceptance-20260817.md` — accepted Private AI communications/documentation RAG deployment at gateway version `0.3.2-alpha.1`.

`edge1-comms-relay-production-readiness-20260815.md` records the earlier production-readiness gate and should be interpreted in its date context.

Later Private AI work may advance the gateway version independently; the dated communications acceptance record remains the history of the `0.3.2-alpha.1` milestone rather than a statement of the gateway's current global version.

## Archive status

The sanitized closeout record is:

`../archive/edge1-comms-relay-news-reader-closeout-20260817.md`

The final protected archive seal record is:

`../archive/edge1-comms-relay-archive-seal-20260817.md`

Archive state is **SEALED**. The authenticated Edge1 inventory completed with `ARCHIVE_SEAL_GATE=PASS`, 16 top-level evidence roots, 138 retained evidence files, 20 exact-duplicate SHA-256 groups covering 73 rows, zero errors, zero unavailable live objects, and byte-for-byte idempotence across two inventory passes.

The protected archive root is `/var/lib/wwcx-deployment-evidence/comms-relay/archive-seal-20260817T023340Z`; its package manifest SHA-256 is `e218e3939ef823d2b36f7a413fb78fad836879bbffd958824254c421008eb3b8`.

The News Reader v2 source record has terminal disposition `unavailable-not-created`: the accepted deployment did not create a dedicated protected evidence directory, and later pathname/marker discovery found none. Its production acceptance remains independently preserved by deployment branch/head and repository acceptance records.

Credential values and the raw live SQLite database remain excluded from Git. The Eternal September credential contents were explicitly excluded from the archive payload; only non-secret metadata was retained.

## Safety boundary

Still separately gated or disabled:

- public IRC or NNTP exposure;
- upstream posting;
- inbound NNTP feeds;
- `IHAVE`, `CHECK`, `TAKETHIS` or streaming federation;
- formal bidirectional peering;
- DNS/firewall/certificate changes for the relay;
- forwarding private `wwcx.*` articles upstream.
