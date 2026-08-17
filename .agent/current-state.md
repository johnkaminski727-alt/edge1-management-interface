# Current State

Last reconciled: 2026-08-17  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Authoritative repository branch: `main`

This file is a concise cross-project state index. Detailed evidence and workstream history remain in the dedicated `.agent/`, acceptance, runbook, register and archive records referenced below.

## Repository versus production checkouts

Do not assume repository `main` is the production checkout for every Edge1 service.

Communications Relay / News Reader accepted production checkout:

```text
branch: deploy/private-nntp-news-reader-v2-20260817
head: 974c7141e18deac92671f81fb1bd3c3ed02a6c68
result: NEWS_READER_V2_DEPLOYMENT=PASS
```

The exact validated News Reader blobs were reconciled into repository history through PR #341, merge commit `6a0397a7f39c07afa3a779c0578e06d165df41e8`. Durable Communications Relay state was reconciled through PR #342, merge commit `1c115663fb23de82e51fcfd0520d91fa196261be`.

Remote `main` also contains separate workstreams. Do not pull/switch the accepted relay checkout to current `main` solely for documentation, archive or history reconciliation.

## Communications Relay — accepted live state

Service: `edge1-comms-relay.service`.

Private listener baseline:

- IRC `127.0.0.1:16667`;
- NNTP `127.0.0.1:1119`;
- control/API/News Reader `127.0.0.1:8100`.

Telephony analytics remains separate on `127.0.0.1:8099`.

Control `/healthz` accepted `status: ok`, version `1.0.0`. Mutation methods remain blocked with HTTP 405. Network exposure and federation remain disabled.

Current accepted ingestion source order:

1. `wwcx-bootstrap`;
2. `eternal.comp.lang.python`;
3. `eternal.news.admin.peering`;
4. `edge1-repository`.

Accepted Eternal September mappings:

- `comp.lang.python` -> `usenet.comp.lang.python`;
- `news.admin.peering` -> `usenet.news.admin.peering`.

Both use outbound TLS reader mode to `news.eternal-september.org:563`. Upstream posting, inbound feeds, streaming federation and formal peering remain disabled.

Accepted provenance state at activation:

- `usenet.comp.lang.python`: 8 external items + 1 `wwcx-bootstrap` introduction, duplicate external source IDs 0;
- `usenet.news.admin.peering`: 8 external items + 1 `wwcx-bootstrap` introduction, duplicate external source IDs 0, wrong-group/orphan/bad-provenance/unexpected-provenance counts 0, ingestion errors since activation 0.

Do not validate imported groups by raw total count alone; use source-specific provenance.

Detailed state:

- `.agent/comms-relay.md`;
- `.agent/comms-relay-upstream-nntp.md`;
- `docs/communications/README.md`.

## Private News Reader v2

Accepted live capabilities:

- newsgroup browsing;
- bounded search;
- exact source filters including native/local, WW.CX Bootstrap, Edge1 Repository and both Eternal September sources;
- 25/50/100 pagination with exact totals and previous/next offsets;
- article body/detail, raw stored headers and provenance;
- threaded and flat-list views using stored `References` / `X-WWCX-Upstream-References` ancestry;
- read-only HTTP mutation enforcement.

Acceptance record:

`docs/communications/edge1-comms-relay-news-reader-live-acceptance-20260817.md`

## Communications Relay archive state

Closeout:

`docs/archive/edge1-comms-relay-news-reader-closeout-20260817.md`

Final seal record:

`docs/archive/edge1-comms-relay-archive-seal-20260817.md`

Status: **SEALED**.

Protected archive root:

`/var/lib/wwcx-deployment-evidence/comms-relay/archive-seal-20260817T023340Z`

Archive package manifest SHA-256:

`e218e3939ef823d2b36f7a413fb78fad836879bbffd958824254c421008eb3b8`

Final reconciliation:

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

The News Reader v2 evidence-root record has terminal disposition `unavailable-not-created`; the accepted deployment did not create a dedicated protected evidence directory and later discovery found none. Production acceptance remains preserved by the accepted deployment branch/head/result and repository acceptance records.

No service, production checkout, DNS, firewall, certificate or credential change was made for archive sealing.

## Security / Network Defense — last accepted workstream state

The previously accepted security baseline remains independently documented:

- Security Correlation and Network Defense live/accepted at its acceptance checkpoint;
- network-source freshness threshold `600` seconds;
- overall Network Defense state recorded as `limited`;
- DNS `not_staged`;
- DNS enforcement false;
- verified enforcement count remained `1` before/after freshness activation;
- traffic controls and timer state unchanged by that activation.

Use the dedicated security acceptance records and a fresh authenticated inspection when present-day security state matters. Communications Relay documentation reconciliation does not re-validate or modify the security workstream.

## Telephony / DTMF — last accepted workstream state

The last recorded accepted telephony baseline includes:

- Asterisk updated from `22.8.2` to `22.10.1` at its acceptance checkpoint;
- DTMF runtime help exposed `0-9`, `*`, `#`, `A-D`;
- offline probe passed RFC 4733 event range `0-15`;
- active runtime/generated PJSIP endpoint-policy reconciliation found zero endpoints, AORs, contacts and transports and zero explicit generated endpoint-policy records at its checkpoint;
- carrier/end-to-end DTMF behavior remains separately gated/unverified unless newer evidence supersedes it;
- provider technical-response state remains tracked in `.agent/dtmf-provider-response-tracker.md`.

No call origination, DTMF transmission, carrier-route change or emergency-path test is implied by these records.

## Alerting compatibility — last accepted workstream state

The offline alerting foundation remains separately documented:

- offline CAP-CP/EBS laboratory installed under `/opt/wwcx-alerting-lab` at its acceptance checkpoint;
- synthetic bilingual CAP-CP structural/lifecycle tests passed;
- no operational CAP feed;
- `Actual` alerts blocked/not accepted by the test-only program;
- no alert call/page origination, tone transmission, carrier route or public distribution enabled by that work.

Historical residual warnings remain subject to fresh verification before action:

1. PJSIP runtime-object visibility versus UDP `127.0.0.1:5061`;
2. SysV-backed Asterisk startup wrapper versus systemd enablement state;
3. Asterisk TCP `8089` non-loopback wildcard listener.

Do not change transports, service-startup policy, certificates, listeners or firewall rules from these notes alone.

## Key Communications Relay protected evidence

The final archive froze every pre-existing top-level directory under `/var/lib/wwcx-deployment-evidence/comms-relay` before creating the archive-seal directory. The authoritative frozen root list and per-file hashes are stored in the protected archive package and summarized in `docs/archive/edge1-comms-relay-archive-seal-20260817.md`.

Do not reopen News Reader evidence-root discovery unless new contrary evidence appears; its terminal archival disposition is `unavailable-not-created`.

## Current continuation order

For Communications Relay:

1. read `docs/communications/README.md`;
2. read `.agent/comms-relay.md` and `.agent/comms-relay-upstream-nntp.md`;
3. use `docs/handoff/edge1-comms-relay-runbook.md`;
4. use dated acceptance records for historical evidence;
5. use `docs/archive/edge1-comms-relay-news-reader-closeout-20260817.md` and `docs/archive/edge1-comms-relay-archive-seal-20260817.md` for the sealed archive record.

For security, telephony, alerting, time authority, private library and other Edge1 workstreams, use their dedicated current state/runbooks and fresh inspection rather than inferring state from Communications Relay records.

## Safety boundary

Do not expose credentials or secret values. Do not change DNS, firewall, certificates, authentication policy, public listeners, production traffic, alert delivery, call/DTMF transmission, carrier routing, upstream posting, inbound NNTP feeds, formal peering, or retained evidence/data solely from this state record. Reversible documentation and read-only inspection remain the default continuation path.
