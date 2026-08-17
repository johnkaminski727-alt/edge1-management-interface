# Edge1 Operations Handoff

Date: 2026-08-17  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Authoritative repository branch: `main`

## Branch and production-checkout discipline

Repository `main` is the integration/history branch, not automatically the production checkout for every Edge1 workstream.

The accepted Communications Relay / News Reader production checkout is intentionally isolated:

```text
branch: deploy/private-nntp-news-reader-v2-20260817
head: 974c7141e18deac92671f81fb1bd3c3ed02a6c68
result: NEWS_READER_V2_DEPLOYMENT=PASS
```

Do not switch/pull the relay production checkout to current `main` solely for documentation, archive, or history reconciliation. Review/deploy unrelated production changes independently.

## Communications Relay — accepted current state

Service: `edge1-comms-relay.service`.

Accepted private listeners:

- IRC `127.0.0.1:16667`;
- NNTP `127.0.0.1:1119`;
- control/API/News Reader `127.0.0.1:8100`.

Accepted source order:

1. `wwcx-bootstrap`;
2. `eternal.comp.lang.python`;
3. `eternal.news.admin.peering`;
4. `edge1-repository`.

Accepted Eternal September mappings:

- `comp.lang.python` -> `usenet.comp.lang.python`;
- `news.admin.peering` -> `usenet.news.admin.peering`.

Both use outbound TLS reader mode to `news.eternal-september.org:563`. Upstream posting, inbound feeds, streaming federation and formal peering remain disabled.

The private News Reader v2 is live on the existing loopback control listener. It provides bounded search, exact source filters, 25/50/100 pagination, article detail/provenance and threaded/flat views. Mutation attempts remain HTTP 405 `read_only_control_api`.

Repository reconciliation:

- PR #341 merged the exact validated News Reader blob set as `6a0397a7f39c07afa3a779c0578e06d165df41e8`;
- PR #337 was closed as superseded development history;
- PR #342 merged durable Communications Relay state as `1c115663fb23de82e51fcfd0520d91fa196261be`;
- PR #344 merged comprehensive documentation/archive preparation as `1610d3c57efac50f30db7780b9875fa3fe6da870`;
- PR #345 recorded the documentation closeout merge point as `6ecd450b84c8cc22e83a4afca6ebded9f48e1f8e`;
- PR #346 merged the final archive seal as `17c3e665bc218862c3b7eb3b28cae856ed4209e7`.

Current documentation index:

`docs/communications/README.md`

Operator runbook:

`docs/handoff/edge1-comms-relay-runbook.md`

## Communications Relay archive handoff

Archive closeout:

`docs/archive/edge1-comms-relay-news-reader-closeout-20260817.md`

Final seal record:

`docs/archive/edge1-comms-relay-archive-seal-20260817.md`

State: **SEALED**.

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

`COMMS-NEWS-READER-V2` has terminal disposition `unavailable-not-created`; the accepted News Reader deployment did not create a dedicated protected evidence directory and subsequent discovery found none. Do not invent or keep searching for a path unless new contrary evidence appears.

The archive inventory covered every pre-existing top-level Communications Relay evidence directory plus relevant config-control history. Credential contents were excluded, exact duplicates were reported/retained, and the two inventory passes were byte-for-byte identical.

Do not move/delete evidence or restart/change the service merely because the archive is sealed.

## Communications Relay readiness rule

`edge1-comms-relay.service` uses systemd `Type=simple`. After restart, `systemctl is-active` can precede socket readiness.

Use bounded `/healthz` plus listener checks. Do not use an immediate one-shot curl as the only post-restart gate.

## Security / Network Defense baseline

Security Correlation and Network Defense remain an independently accepted production workstream. The previously accepted network-source freshness threshold is `600` seconds, DNS remains `not_staged`, and DNS enforcement remains false according to the last recorded acceptance for that workstream.

Do not infer that the Communications Relay closeout re-validates or changes the security workstream. Use its dedicated state, acceptance records and fresh host inspection when current security state matters.

## Alerting / telephony baseline

The last recorded accepted alerting/telephony baseline includes:

- Asterisk `22.10.1` installed/running at its acceptance checkpoint;
- offline CAP-CP/EBS laboratory under `/opt/wwcx-alerting-lab`;
- synthetic bilingual CAP-CP structural/lifecycle tests passed;
- no CAP feed, `Actual` alert handling, alert origination, call/page route, tone transmission, carrier route or public distribution enabled by that program;
- carrier/end-to-end DTMF behavior remains separately gated and unverified unless newer evidence supersedes it.

Use the dedicated telephony/alerting acceptance records and `.agent/dtmf-provider-response-tracker.md` before continuing that work.

## Residual alerting warnings from the last recorded handoff

These are historical unresolved warnings until a newer authenticated inspection supersedes them:

1. `pjsip show transports` returned no objects although Asterisk owned UDP `127.0.0.1:5061`;
2. the generated legacy SysV-backed Asterisk wrapper was active while systemd enablement reported disabled;
3. Asterisk TCP `8089` was bound to a non-loopback wildcard address.

Do not change transports, startup policy, TLS/certificates, listener addresses or firewall rules based on these notes alone. Re-inspect current state first.

## Repository documentation hierarchy

For Communications Relay continuation, use in order:

1. `docs/communications/README.md`;
2. `.agent/comms-relay.md`;
3. `.agent/comms-relay-upstream-nntp.md`;
4. `docs/handoff/edge1-comms-relay-runbook.md`;
5. dated acceptance records;
6. `docs/archive/edge1-comms-relay-news-reader-closeout-20260817.md`;
7. `docs/archive/edge1-comms-relay-archive-seal-20260817.md`;
8. current GitHub history/PRs;
9. fresh authenticated Edge1 inspection when live state matters.

## Safety boundary

No DNS, Unbound, RPZ, nftables, firewall, certificate, authentication-policy, public-listener, production-traffic, alert-feed, `Actual` alert, call/page origination, tone/DTMF transmission, carrier routing, upstream posting, inbound NNTP feed, formal peering, credential disclosure, evidence deletion, or data deletion is authorized merely by this handoff.
