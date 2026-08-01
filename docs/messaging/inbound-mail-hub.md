# WW.CX Inbound Mail Hub

## Status

Implemented as a disabled, loopback-only routing foundation. No MX record, mailbox rule, SMTP listener, firewall rule, reverse-proxy route, credential, provider setting, or production mail flow is changed by this branch.

The hub complements the outbound-mail compliance gateway. Together they form a provider-neutral correspondence control plane:

```text
Internet sender
  -> current or future MX/provider
  -> authenticated provider webhook or trusted local-MTA adapter
  -> WW.CX inbound mail hub
       -> explicit recipient route
       -> quarantine for unknown managed-domain recipients
       -> reject unmanaged domains
       -> minimal append-only audit event

WW.CX admin / workflow
  -> outbound compliance gateway
  -> approved provider
  -> recipient
```

## Why the first adapter is not a public SMTP listener

Running a direct MX requires a production MTA, public TCP 25 reachability, reverse DNS, TLS, queue management, spam and malware controls, abuse handling, bounce behavior, monitoring, patching, backup MX decisions, and a tested rollback. The current foundation therefore accepts normalized envelopes only from an authenticated provider webhook or a trusted local MTA on the private boundary.

This lets WW.CX centralize routing and audit behavior without turning the operations API into an Internet-facing mail server.

## Current routing behavior

The committed configuration manages `ww.cx` and defines explicit routes for:

- `john@ww.cx`;
- `postmaster@ww.cx`;
- `abuse@ww.cx`.

All three currently target the existing `john@ww.cx` mailbox. Unknown addresses at `ww.cx` are quarantined rather than silently discarded. Recipients outside configured domains are rejected by the routing engine.

The configuration is data-driven, so additional domains and aliases can be added without changing the routing code. Catch-all routing is intentionally not enabled because it increases spam load and can hide address mistakes.

## API

```text
GET  /mail-hub/healthz
GET  /mail-hub/status
GET  /mail-hub/audit?limit=50
GET  /mail-hub/quarantine?limit=50
POST /mail-hub/ingest
```

The service binds only to loopback. Production access must be provided through an authenticated internal reverse proxy or a local MTA adapter.

`POST /mail-hub/ingest` expects a normalized JSON envelope and the `X-WWCX-Inbound-Token` header. A provider-specific adapter should verify the provider's native signature first, then translate the event into this contract.

Example normalized request:

```json
{
  "envelope_from": "sender@example.com",
  "recipients": ["john@ww.cx"],
  "message_size": 4096,
  "provider_message_id": "provider-specific-id",
  "subject": "Example subject"
}
```

The current contract deliberately does not accept raw MIME content. That prevents accidental message-body or attachment persistence before encrypted content storage, malware scanning, retention, access control, and privacy procedures are selected.

## Data minimization

Audit records include:

- event timestamp;
- SHA-256 of provider message ID;
- SHA-256 of envelope sender;
- SHA-256 of subject;
- message size and recipient count;
- per-recipient routing decisions.

They do not include:

- raw provider message IDs;
- message bodies;
- attachment bytes;
- raw MIME content;
- authentication tokens.

Quarantine records contain routing metadata only. A later content quarantine needs encrypted storage, malware scanning, access control, retention, deletion, and export procedures.

## Activation gates

Production routing requires all of the following:

1. hub `enabled`;
2. deployment authorization;
3. production-routing authorization;
4. an enabled non-disabled ingress profile;
5. a runtime ingress secret;
6. authenticated operations routing;
7. a selected MX or inbound provider;
8. verified recipient and alias inventory;
9. spam, malware, bounce, abuse, and queue procedures;
10. controlled delivery tests to WW.CX-owned mailboxes;
11. documented rollback;
12. explicit authorization for the MX or provider-routing cutover.

The committed configuration fails these gates by design.

## Recommended first production topology

The lowest-risk initial topology is:

```text
Existing hosted mail provider remains MX
  -> provider route/journal/webhook for selected addresses
  -> authenticated WW.CX inbound hub
  -> existing mailbox destination
```

This supports a shadow or pilot mode before any full-domain cutover. A dedicated MTA on Edge1 can be evaluated later, but it should not be the first production dependency unless TCP 25, PTR, reputation, filtering, queue operations, and redundancy are already proven.

## Cutover sequence

1. Inventory all current WW.CX domains, mailboxes, aliases, forwarders, mailing lists, and catch-all behavior.
2. Confirm the current authoritative MX and provider account.
3. Add inbound hub routes for every known recipient while the hub remains disabled.
4. Deploy the loopback service and authenticated internal route.
5. Configure one provider webhook or local-MTA adapter with runtime secrets.
6. Replay synthetic envelopes and verify route, quarantine, and audit behavior.
7. Pilot one non-critical alias or copied/journaled flow.
8. Verify delivery, duplicates, loops, bounces, and rollback.
9. Authorize and execute the provider-routing or MX change separately.

## Relationship to the outbound gateway

The inbound and outbound services should eventually share a single correspondence matrix keyed by WW.CX control ID, provider message ID hashes, RFC Message-ID hashes, case ID, sender, recipients, delivery status, replies, and quarantine state. Message content should remain in the authoritative mailbox or encrypted records store rather than the audit ledger.
