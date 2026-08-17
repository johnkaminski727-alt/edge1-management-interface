# Validation State

Last verified: 2026-08-17

## Communications Relay / upstream NNTP / News Reader closeout

Current sanitized acceptance chain:

- relay service accepted private on loopback;
- local automatic ingestion accepted;
- `eternal.comp.lang.python` accepted live;
- `eternal.news.admin.peering` accepted live;
- private News Reader v2 accepted live;
- exact validated News Reader blobs reconciled to repository `main` through PR #341;
- durable state reconciled through PR #342;
- comprehensive documentation/archive preparation reconciled through PR #344 and PR #345;
- protected archive seal reconciled through PR #346.

Accepted News Reader production checkout:

```text
branch: deploy/private-nntp-news-reader-v2-20260817
head: 974c7141e18deac92671f81fb1bd3c3ed02a6c68
result: NEWS_READER_V2_DEPLOYMENT=PASS
```

Accepted loopback listeners:

```text
127.0.0.1:1119   NNTP
127.0.0.1:16667  IRC
127.0.0.1:8100   control/API/News Reader
```

Validated live behavior includes:

- relay health `ok`, version `1.0.0`;
- production-readiness test passed;
- controlled-ingestion regression passed;
- upstream NNTP TLS validation passed;
- config-control metadata validation passed;
- News Reader threaded pagination/source-filter validation passed;
- JavaScript syntax passed;
- exact Eternal September filtering passed;
- bootstrap-only filtering passed;
- HTTP mutation attempts remained 405 `read_only_control_api`;
- duplicate external source IDs remained zero;
- listener posture remained loopback-only;
- second-source wrong-group/orphan/bad-provenance/unexpected-provenance counts were zero at acceptance;
- second-source ingestion errors since activation were zero at acceptance.

Service-readiness rule:

- `edge1-comms-relay.service` uses `Type=simple`;
- `systemctl is-active` is not an application-readiness signal;
- bounded `/healthz` plus listener verification is required after restart.

Archive state:

```text
docs/archive/edge1-comms-relay-news-reader-closeout-20260817.md
docs/archive/edge1-comms-relay-archive-seal-20260817.md
status: SEALED
```

Protected archive root:

```text
/var/lib/wwcx-deployment-evidence/comms-relay/archive-seal-20260817T023340Z
```

Final archive validation:

```text
ARCHIVE_SEAL_GATE=PASS
inventory_idempotence=PASS
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
archive_package_manifest_sha256=e218e3939ef823d2b36f7a413fb78fad836879bbffd958824254c421008eb3b8
```

`COMMS-NEWS-READER-V2` has terminal archival disposition `unavailable-not-created`: the accepted deployment did not create a dedicated protected evidence directory and later discovery found none. Production acceptance remains independently established by the accepted branch/head/result and repository acceptance records.

The final archive froze all 16 pre-existing top-level Communications Relay evidence directories and relevant config-control history. Credential contents were explicitly excluded. Live config/SQLite were hashed and metadata-recorded without being committed. Exact duplicates were reported/retained. Two complete evidence-inventory passes were byte-for-byte identical.

The live production checkout must not be moved to current remote `main` solely for documentation/archive reconciliation.

## DTMF provider technical-response intake live acceptance

Authenticated execution on `edge1.ww.cx` as `wwadmin` completed against a clean `main` checkout at:

```text
faaf7b04c5fd3648b42b9266eb2cf5fea0f2a5a7
```

Protected evidence:

```text
/var/lib/wwcx-deployment-evidence/repository-metadata-repair/20260801T180347Z/dtmf-provider-response-intake-sync-20260801T210156Z
```

Final evidence-manifest SHA-256:

```text
fe414802b5e52089673e3231693fbc1cb89c615c65e1450d670d77bcb03d7db4
```

Validated results:

- repository synchronized from `92cdccd4c7bda627bd7c5e8986bd0ed301c0ccb7` to `faaf7b04c5fd3648b42b9266eb2cf5fea0f2a5a7`;
- repository state was clean on branch `main`;
- Git index ownership remained `wwadmin:wwadmin`, mode `0600`, with no repair required;
- technical-response schema and pending example JSON were valid;
- all nine required response questions occurred exactly once;
- service-guarantee scope and pending-state gates were present;
- provider-evidence intake tests passed;
- provider technical-response intake tests passed;
- Asterisk DTMF readiness validation passed;
- pending technical-response validation passed;
- `response_state=pending`;
- `matrix_update_allowed=false`;
- `live_test_authorized=false`;
- no provider technical reply had been received;
- Asterisk and telephony-analytics service state did not change;
- no service restart, runtime change, call, DTMF transmission, route change, or carrier-matrix promotion occurred;
- the initial brittle documentation-string failure was retained and corrected with a structural nine-question validation;
- the final SHA-256 manifest verified every retained evidence file.

Acceptance record:

```text
docs/telephony/dtmf-provider-response-intake-edge1-acceptance-20260801.md
```

Tracker:

```text
.agent/dtmf-provider-response-tracker.md
```

The three dangling tree objects reported by `git fsck --connectivity-only` were informational; connectivity validation exited successfully.

## DTMF provider-public evidence live acceptance

Authenticated execution on `edge1.ww.cx` as `wwadmin` completed against a clean `main` checkout at:

```text
ccb824c35cc54fa2d210ca7d03eb4cbb2ae39dc1
```

Required repository history present:

```text
provider-public evidence capability merge: 31fb4865f409bcf474ffd3d2c61a1727161cbe4c
repository acceptance merge: 4207d39306960faa5532af23e50a2c43258f6d01
```

Protected evidence:

```text
/var/lib/wwcx-deployment-evidence/repository-metadata-repair/20260801T180347Z/dtmf-provider-evidence-repair-sync-20260801T194349Z
```

Final evidence-manifest SHA-256:

```text
09ea7aafdb274e50b948d31c5eb5304b3960e22abbcd79e23f5d5aec690e64a4
```

Validated results:

- one root-owned Git metadata entry, `.git/index`, was repaired to `wwadmin:wwadmin`;
- index mode remained `0600` and its contents were preserved during the ownership repair;
- repository state was clean;
- DTMF provider-evidence intake tests passed;
- Asterisk DTMF readiness validation passed;
- the provider-public evidence record passed validation;
- matrix-to-evidence cross-record validation passed;
- in-band fallback is `documented` with no codec constraint;
- RFC 4733 and its event range remain `unknown`;
- SIP INFO and extended `A-D` remain `unknown`;
- carrier interoperability remains `partially-documented` and end-to-end behavior remains unverified;
- live-test authorization remains false;
- Asterisk and telephony-analytics service state did not change;
- no service restart, runtime change, call, DTMF transmission, or route change occurred;
- the initial failed-heredoc output was retained and the corrected validation completed successfully;
- the final SHA-256 manifest verified every retained evidence file.

Acceptance record:

```text
docs/telephony/dtmf-provider-public-evidence-live-acceptance-20260801.md
```

The three dangling tree objects reported by `git fsck --connectivity-only` were informational; connectivity validation exited successfully.
