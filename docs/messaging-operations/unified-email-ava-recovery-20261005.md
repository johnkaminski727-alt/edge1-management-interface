# Unified email gateway and AVA recovery — 2026-10-05

## Recovered direction

Use the stable `mail.ww.cx` service identity. Initially retain `ww.cx` on Namecheap Private Email, with `blank@ww.cx` as the physical catch-all target and `domaincontact@ww.cx` as a distinct administrative identity. Migrate Creekco, Spirit Creek Gardens, scgardens.ca, then Omegafx one domain at a time. Preserve each original SMTP recipient and provider rollback path. Receiving a catch-all message never authorizes sending from that address.

## Evidence and limits

Source baseline: `phase-3o-ava-reconciliation-20261002`, commit `3ee8b772` (latest recovered AVA reconciliation branch). August records document successful provider header access, bounded provider-native ingestion, and local Postfix archive-first intake. These are historical acceptance records, not proof of the current post-rebuild runtime. All four attempted connected operator calls (messaging status, capabilities, identity, git state) returned tool-not-found in this session. No live email, database, credentials, DNS or service configuration was accessed or changed.

## Implemented increment

The persisted Mail Room previously offered status and exact-ID message/thread reads but no discovery. Added bounded recent-mail listing and literal subject/sender search, exact recipient filtering, pagination and identifiers for subsequent reads. Search excludes synthetic/legacy/non-authoritative rows inside SQL before pagination and omits message bodies. A SQLite work budget stops costly scans. Email text remains untrusted.

The authenticated endpoint is `GET /outbound-mail/api/v1/correspondence/search?q=...&recipient=...&limit=25&offset=0`. Only the existing `wwcx-private-ai` client can use it. The complete query string is signed, so filters cannot be changed independently of authentication. Correspondence request logs redact query/identifier details. Runtime applications, BigBird client/facade and the tool manifest expose the new operation; this does not prove registration in the separately installed AVA gateway.

## Next operator evidence

On **edge1**, from the intended source checkout, run:

```bash
# TARGET: edge1 — read-only; no mailbox login or restart
cd /opt/edge1-management-interface
python3 tools/messaging/unified_email_runtime_preflight.py
```

This new script requires the reviewed source to be available on Edge1 first. It outputs aggregate service/store state and selected Postfix parameters, without message content, credentials or environment dumps. It does not require overwriting the current working tree. If the database cannot be read by the operator, report that result; do not broaden its permissions.

## Completion sequence

1. Establish current source revision, local changes, service state, private store provenance, ownership and restore availability. Preserve live changes before any source deployment.
2. Restore/commission local Mail Room and AVA authenticated read/search wiring; verify real message discovery in AVA and the private UI.
3. Complete a durable provider polling design with bounded fetches, UIDVALIDITY handling, deduplication, retry/backoff, protected secrets and observable failures; verify scanner/quarantine behavior and original-recipient evidence.
4. Verify current public DNS, PTR, certificate, TCP/25 reachability, relay denial and backup restoration before proposing a concrete public-ingress cutover. August DNS observations are stale.
5. Perform one-domain migration and incoming acceptance with rollback; retain provider fallback until delivery is accepted.
6. Commission outbound sender identities and signed, scanned, approved delivery separately; then add narrowly delegated AVA triage, summaries, draft replies and follow-ups. Auto-send/quarantine release remain outside this increment.

Repository tests are engineering evidence, not live commissioning. Current work does not yet deliver a production unified inbox, persistent polling, public SMTP ingress, or AVA sending.
