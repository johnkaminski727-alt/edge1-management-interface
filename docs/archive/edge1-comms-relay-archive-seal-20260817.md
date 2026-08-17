# Edge1 Communications Relay Archive Seal

Date: 2026-08-17  
System: `edge1.ww.cx`  
Classification: sanitized archive-seal record  
Archive result: **SEALED**

## Host-side acceptance

The final authenticated archive inventory completed on Edge1 with:

```text
ARCHIVE_SEAL_GATE=PASS
inventory_idempotence=PASS
errors=0
live_object_unavailable=0
```

The relay remained enabled, active, and healthy during the read-only archive operation. No service restart, runtime configuration change, database mutation, listener change, DNS/firewall/certificate change, or credential disclosure occurred.

## Protected archive package

Protected archive root:

```text
/var/lib/wwcx-deployment-evidence/comms-relay/archive-seal-20260817T023340Z
```

Archive package manifest SHA-256:

```text
e218e3939ef823d2b36f7a413fb78fad836879bbffd958824254c421008eb3b8
```

The protected archive package contains:

- `credential-exclusion.json`;
- `evidence-inventory-pass1.jsonl`;
- `evidence-inventory-pass2.jsonl`;
- `evidence-roots.txt`;
- `exact-duplicates.tsv`;
- `exceptions.tsv`;
- `live-objects.jsonl`;
- `source-ledger.tsv`;
- `summary.txt`.

## Reconciliation totals

Final sanitized totals:

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

The `COMMS-NEWS-READER-V2` source record has terminal disposition `unavailable-not-created`. No dedicated News Reader v2 protected deployment-evidence directory was created by the accepted deployment procedure, and subsequent path/marker discovery found none. This is not treated as a missing retained artifact. Production acceptance is independently preserved by the accepted deployment branch/head and the repository acceptance records.

Accepted News Reader production provenance:

```text
branch: deploy/private-nntp-news-reader-v2-20260817
head: 974c7141e18deac92671f81fb1bd3c3ed02a6c68
result: NEWS_READER_V2_DEPLOYMENT=PASS
```

## Manifest hashes

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

The two evidence inventory passes were byte-for-byte identical before seal acceptance.

## Credential exclusion

`/etc/wwcx/credentials/eternal-september.json` was handled as an explicit credential-content exclusion. Only non-secret metadata was recorded. Credential contents were not committed to Git and were not included in the evidence inventory payload.

## Duplicate handling

Twenty exact-duplicate SHA-256 groups covering 73 inventory rows were reported and retained. Exact duplicates were not silently deleted or consolidated. Materially different versions remain separate archive records.

## Repository records

Repository documentation/archive preparation was reconciled through:

- PR #341 — exact validated News Reader integration;
- PR #342 — durable Communications Relay state;
- PR #344 — comprehensive Communications Relay documentation/archive preparation;
- PR #345 — documentation closeout merge-point record.

This seal record is the final sanitized repository record for the protected archive operation. Git history for the merge of this record is the authoritative repository seal point.

## Safety and retention

The protected archive is an evidence record, not a signal to delete operational or historical material.

Do not delete, prune, rewrite, or relocate retained source evidence merely because this seal exists. Do not commit the live SQLite database, credential contents, private account material, or raw protected evidence to the public repository.
