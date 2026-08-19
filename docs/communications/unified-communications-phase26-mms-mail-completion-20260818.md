# Unified Communications Phase 26 — MMS / Mail completion

Date: 2026-08-18

## Scope

This increment completes the scanner-independent MMS quarantine engineering that can be safely finished without inventing a malware engine, and re-audits the Mail Room correspondence-read source boundary.

## MMS private quarantine storage

Repository implementation now includes a content-addressed private blob store at `services/wwcx-messaging-gateway/app/quarantine_storage.py`.

Security properties:

- deterministic attachment IDs derived only from verified SHA-256 content digests;
- bounded streaming ingestion with configurable size limit;
- expected SHA-256 verification before content becomes an accepted quarantine object;
- provider URL and provider filename never determine storage paths;
- sanitized optional display filename only;
- private directory mode `0700` and private regular-file mode `0600` enforcement;
- symlink-root rejection and regular-file checks;
- content metadata and trusted scan state stored separately;
- append-only local audit events without provider media URLs;
- duplicate content reuses only a previously verified content-addressed object;
- restart/recovery verifies the persisted digest and byte count before use;
- retention expiry produces `retention_expired_held`; it does not delete or release content automatically;
- no web-serving API and `web_served=false` in the bounded record projection;
- `release_authorized=false` in every ingestion, scan-state and lifecycle projection.

If metadata persistence fails after a private blob has been atomically finalized, the operation reports failure and the blob remains private/held for later operator reconciliation rather than deleting evidence or treating the attachment as accepted.

## Trusted scanner adapter boundary

`app/media_quarantine.py` now has a narrow `TrustedMediaScanner` protocol that receives only a digest-verified private blob path, digest, content type and bounded timeout value. The adapter must enforce its own timeout.

There is deliberately no generic shell command, user-configurable executable hook or arbitrary scanner command. Controlled test doubles validate software behavior only and are not evidence that a production scanner exists.

Fail-closed outcomes include scanner unavailable, timeout, exception, unexpected verdict and blob integrity failure. A clean verdict produces `scanned_clean_held`; it never releases content.

## Test coverage

`tests/test_private_media_quarantine.py` covers:

- valid private ingestion;
- digest mismatch;
- duplicate digest/content;
- missing digest;
- malformed media metadata;
- oversized input;
- scanner absent/unavailable;
- scanner timeout;
- scanner exception;
- malicious result;
- clean result remaining held;
- unexpected scanner result;
- storage failure;
- restart/recovery;
- retention expiry remaining held;
- post-ingest integrity mutation;
- private permissions and symlink-root rejection.

## Runtime acceptance state

Repository implementation does not establish a trusted scanner runtime. No trusted scanner engine was found in the inspected repository evidence, no external scanning service is authorized for private MMS content, and ClamAV must not be installed on Edge1 merely to clear this gate.

Therefore MMS security remains **degraded / runtime-blocked** until both of these are true on an approved private runtime:

1. the private quarantine store is deployed and its ownership/modes/restart behavior are accepted; and
2. a genuinely trusted scanner adapter/runtime is attached and evidenced.

The smallest remaining scanner action is to identify or provision an approved private scanner runtime outside the constrained Edge1 host, then implement only its concrete adapter behind `TrustedMediaScanner` and run the existing fail-closed acceptance suite against real permitted scanner evidence. Private MMS media must not be uploaded to a third party without separate authorization.

## Mail Room correspondence source audit

The existing Mail Room source inspection found:

- `mail_threading.py` validates explicit correspondence/thread correlation metadata but explicitly does not create or infer message history;
- `inbound_mail_hub.py` normalizes and routes authenticated inbound envelopes and emits minimized audit evidence; it is not a persisted authoritative message-body/thread store;
- `mail_ai_adapter.py` correctly keeps `mail.correspondence.read` at `blocked_pending_authoritative_source`.

No authoritative native correspondence store was identified that can safely back `mail.correspondence.read`. Outbound audit metadata, logs, UI scraping, synthesized threads and external mailboxes are not substituted for that source.

The smallest architectural decision needed to unblock Mail is to explicitly select and authorize the native authoritative correspondence store/intake source. Only then should a bounded read-only adapter be added and accepted against real permitted records.

## Repository reconciliation

PR #414 is already merged. Its accepted local Asterisk/PJSIP repair does not establish current external carrier/interconnect health; external Voice/SIP health remains unknown without a permitted fresh peer/interconnect probe.

No production SMS/MMS, email, call, route, quarantine release, credential, DNS, firewall or security-policy change is part of this increment.
