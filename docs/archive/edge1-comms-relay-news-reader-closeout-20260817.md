# Edge1 Communications Relay / Upstream NNTP / News Reader Closeout

Date: 2026-08-17  
Classification: sanitized operational closeout  
System: `edge1.ww.cx`  
Repository: `johnkaminski727-alt/edge1-management-interface`

## Archive status

**SEALED.**

The authenticated host-side archive inventory completed with `ARCHIVE_SEAL_GATE=PASS`. Repository documentation, sanitized acceptance records, the complete top-level Communications Relay evidence boundary, explicit exclusions, live-object hash metadata, duplicate accounting, terminal unavailable-source disposition, and production-checkout boundary are reconciled.

Final protected seal record:

`docs/archive/edge1-comms-relay-archive-seal-20260817.md`

Protected archive root:

`/var/lib/wwcx-deployment-evidence/comms-relay/archive-seal-20260817T023340Z`

Archive package manifest SHA-256:

`e218e3939ef823d2b36f7a413fb78fad836879bbffd958824254c421008eb3b8`

No source evidence should be moved, deleted, compressed, rewritten, or pruned merely because the archive is sealed.

## Accepted production scope

The closeout covers:

1. private Edge1 IRC/NNTP Communications Relay;
2. founder/local identity activation;
3. automatic bootstrap and Edge1 repository ingestion;
4. selective outbound Eternal September NNTP reader integration;
5. accepted `comp.lang.python` mapping;
6. accepted `news.admin.peering` mapping;
7. private read-only News Reader v2;
8. repository reconciliation and durable state documentation;
9. protected host-side evidence inventory and archive seal.

It does not cover public protocol exposure, inbound NNTP feeds, formal peering, upstream posting, DNS/firewall/certificate changes, or forwarding private `wwcx.*` articles upstream.

## Repository chain of custody

Important repository milestones:

- upstream NNTP implementation floor: `c7b4b2c9124e072abaa356f0645e10d449c38eea`;
- News Reader validated development head: `b06233c0ce2210b58f9fe88ccb2b64cd14a959f6`;
- News Reader production deployment head: `974c7141e18deac92671f81fb1bd3c3ed02a6c68`;
- PR #341 merge commit: `6a0397a7f39c07afa3a779c0578e06d165df41e8` — exact validated News Reader integration;
- PR #342 merge commit: `1c115663fb23de82e51fcfd0520d91fa196261be` — durable relay state;
- PR #337: closed as superseded development history, not merged;
- PR #344 merge commit: `1610d3c57efac50f30db7780b9875fa3fe6da870` — comprehensive documentation/archive preparation;
- PR #345 merge commit: `6ecd450b84c8cc22e83a4afca6ebded9f48e1f8e` — documentation closeout merge-point record.

Git history for the final archive-seal documentation merge is the authoritative repository seal point.

## Production checkout boundary

The accepted News Reader production checkout remains intentionally separate from repository `main`:

- branch: `deploy/private-nntp-news-reader-v2-20260817`;
- head: `974c7141e18deac92671f81fb1bd3c3ed02a6c68`;
- result: `NEWS_READER_V2_DEPLOYMENT=PASS`.

Do not update the live Edge1 checkout merely to make it resemble repository history. Unrelated work on `main` requires its own review and production acceptance.

## Final evidence boundary

The host-side seal froze every pre-existing top-level directory under:

`/var/lib/wwcx-deployment-evidence/comms-relay`

before creating the seal directory. Sixteen top-level evidence roots were discovered and retained:

1. `/var/lib/wwcx-deployment-evidence/comms-relay/20260815T181730Z`;
2. `/var/lib/wwcx-deployment-evidence/comms-relay/20260815T182259Z`;
3. `/var/lib/wwcx-deployment-evidence/comms-relay/20260815T183129Z`;
4. `/var/lib/wwcx-deployment-evidence/comms-relay/20260815T191922Z`;
5. `/var/lib/wwcx-deployment-evidence/comms-relay/20260815T225037Z`;
6. `/var/lib/wwcx-deployment-evidence/comms-relay/20260815T225527Z`;
7. `/var/lib/wwcx-deployment-evidence/comms-relay/auto-ingest-20260815T191918Z`;
8. `/var/lib/wwcx-deployment-evidence/comms-relay/control-port-migration-20260815T183128Z`;
9. `/var/lib/wwcx-deployment-evidence/comms-relay/eternal-news-admin-peering-live-20260816T002007Z`;
10. `/var/lib/wwcx-deployment-evidence/comms-relay/eternal-news-admin-peering-live-20260816T005124Z`;
11. `/var/lib/wwcx-deployment-evidence/comms-relay/eternal-news-admin-peering-prep-20260816T001246Z`;
12. `/var/lib/wwcx-deployment-evidence/comms-relay/eternal-september-live-20260815T233435Z`;
13. `/var/lib/wwcx-deployment-evidence/comms-relay/founder-account-20260815T183745Z`;
14. `/var/lib/wwcx-deployment-evidence/comms-relay/upstream-nntp-20260815T225026Z`;
15. `/var/lib/wwcx-deployment-evidence/comms-relay/upstream-nntp-20260815T225524Z`;
16. `/var/lib/wwcx-deployment-evidence/comms-relay/upstream-nntp-recovery-20260815T230816Z`.

`/var/lib/wwcx-comms/config-control` was also included in the evidence-file inventory as relevant configuration-control history.

## News Reader v2 evidence disposition

`COMMS-NEWS-READER-V2` has terminal disposition:

`unavailable-not-created`

The accepted News Reader v2 deployment procedure did not create a dedicated protected deployment-evidence directory. Subsequent pathname and accepted branch/head/result marker searches under `/var/lib/wwcx-deployment-evidence` returned no candidate. The closeout therefore records the absence explicitly rather than inventing a path.

This is not treated as a missing retained artifact. News Reader production acceptance remains independently established by:

- deployment branch `deploy/private-nntp-news-reader-v2-20260817`;
- deployment head `974c7141e18deac92671f81fb1bd3c3ed02a6c68`;
- result `NEWS_READER_V2_DEPLOYMENT=PASS`;
- dated acceptance record `docs/communications/edge1-comms-relay-news-reader-live-acceptance-20260817.md`;
- exact reader integration through PR #341.

## Final reconciliation

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
```

Twenty exact-duplicate SHA-256 groups covering 73 file rows are retained and reported. Duplicate records were not silently deleted or collapsed.

Two complete evidence-inventory passes were byte-for-byte identical.

## Final manifest hashes

```text
roots_sha256=b322bf286c7496f8e55f0ae5701590392ffbd7318da9a4c28beafe0506131981
source_ledger_sha256=d7c76f258a65a164a967797f98d0128351d91b7ea5aa9f2cc4fd946cfb5d3541
exceptions_sha256=ad18741e801394b8bf56fee777cedd47a49758248e55f0ff33b37f94bf00a327
evidence_inventory_sha256=19c99641a72e8d7218e27f15f9247bcad9a8e8b0e20a640a2b2985d90809bf77
duplicates_sha256=cce6652075b310b9dbb02c91ddea94048f27396c1f71b07d0f234fef9eebab16
live_objects_sha256=b84020a1bf046b376e79ef0d3ef1093e5222a0eb58c14b7200861d5a2f4f58e5
credential_exclusion_sha256=21d459ee1da36ead73bee3fb2cfe88c17e9c335054b82ba5a9adcf50825cd596
archive_package_manifest_sha256=e218e3939ef823d2b36f7a413fb78fad836879bbffd958824254c421008eb3b8
```

## Live restricted objects

The seal recorded hash/metadata for the live canonical config and SQLite database without copying either into Git:

- `/etc/wwcx/comms-relay.json`;
- `/var/lib/wwcx-comms/comms.sqlite3`.

`live_object_unavailable=0`.

The SQLite database remains a restricted operational/archive object because it can contain article bodies, local identity state, password-derivation material, and other private data.

## Credential exclusion

`/etc/wwcx/credentials/eternal-september.json` contents were explicitly excluded. The archive records non-secret metadata/exclusion state only. Credential contents, passwords, private keys, tokens, cookies, and authentication transcripts are not part of the repository archive.

## Sanitized repository records to retain

Current and historical records include:

- `docs/communications/README.md`;
- `docs/communications/edge1-comms-relay-architecture.md`;
- `docs/communications/edge1-comms-relay-ingestion.md`;
- `docs/communications/edge1-comms-relay-upstream-nntp.md`;
- `docs/communications/edge1-comms-relay-upstream-nntp-validation.md`;
- `docs/communications/edge1-comms-relay-news-reader.md`;
- `docs/handoff/edge1-comms-relay-runbook.md`;
- dated relay, ingestion, first-source, second-source, and News Reader acceptance records;
- `.agent/comms-relay.md`;
- `.agent/comms-relay-upstream-nntp.md`;
- `docs/archive/edge1-comms-relay-archive-seal-20260817.md`;
- this closeout record.

Historical acceptance records remain immutable operational history unless a separate factual correction record is required.

## Completion gate

Archive completion requirements are satisfied:

- actual evidence-tree boundary enumerated to a terminal top-level directory set;
- every retained evidence file hashed;
- live config and SQLite metadata/hash captured without committing private objects;
- credential contents excluded;
- exact duplicates distinguished and retained;
- unavailable News Reader source record given a terminal, evidence-backed disposition;
- totals reconcile;
- inventory rerun is idempotent;
- final protected archive package manifest exists;
- no production checkout or service change was made solely for archive housekeeping.

## Resume point

The Communications Relay archive is sealed. Future Communications Relay work should start from the living documentation and accepted production state, not by reopening this archive. Reopen archival investigation only if a factual discrepancy, new retained historical source, integrity failure, or explicitly authorized superseding archive action requires it.
