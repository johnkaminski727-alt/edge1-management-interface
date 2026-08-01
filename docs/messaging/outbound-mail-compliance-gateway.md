# WW.CX Outbound Mail Compliance Gateway

## Status

The gateway is implemented as a disabled, loopback-only preview and policy service. No SMTP relay, provider credential, mailbox setting, DNS record, signing key, production route, or live outbound-message flow is enabled by the committed configuration.

The gateway now shares the multi-domain identity registry with the inbound hub and automatically replaces untrusted sender fields before preview or submission.

## Canonical mail addresses

The identity registry defines three different functions:

- **`john-inbox@ww.cx`** — private inbound delivery mailbox for every `john@...` identity;
- **`maildesk@ww.cx`** — separate inbound delivery mailbox for company and role identities;
- **`noreply@ww.cx`** — outbound-only system identity for messages that intentionally do not invite replies.

The two delivery mailboxes are internal plumbing and are not public sender identities. `noreply@ww.cx` is not an inbound mailbox destination.

## Automatic sender replacement

The gateway does not trust a submitted `From:` or `Reply-To:` value. The identity-aware facade selects the sender in this order:

1. `system_generated=true` selects `noreply@ww.cx` and removes `Reply-To`;
2. a registered `original_recipient` selects the same identity that received the inbound message;
3. an approved identity hint selects a registered non-system identity;
4. otherwise the gateway uses `john@ww.cx` as the default sender.

An unknown original recipient is rejected. A submitted `From:` address cannot override the selected identity. A submitted `Reply-To:` is replaced with the selected sender for ordinary correspondence.

`noreply@ww.cx` is not included in the manual identity list and cannot be selected through an identity hint. It requires the explicit system-generated flag.

Examples:

```text
original_recipient = john@spiritcreekgardens.com
selected From       = john@spiritcreekgardens.com
selected Reply-To   = john@spiritcreekgardens.com

original_recipient = support@creekco.ca
selected From       = support@creekco.ca
selected Reply-To   = support@creekco.ca

system_generated = true
selected From    = noreply@ww.cx
Reply-To         = omitted
```

## Sender activation boundary

Automatic selection does not authorize sending. The committed identity registry has:

```text
outbound_activation_authorized = false
live_sender_allowlist = []
```

A preview can show the selected identity, but a live send is blocked unless that exact address has been provider-verified, added to the live sender allowlist, and all gateway and policy activation gates are satisfied.

This prevents the gateway from selecting an identity that the provider would rewrite, reject, or treat as spoofed.

## Product goal

Provide one approachable admin workspace for correspondence sent from the WW.CX site, ChatGPT-assisted workflows, internal tools, forms, and later approved SMTP or provider-API clients.

The gateway provides:

- automatic identity selection;
- recipient, subject, message-class, case-ID, and action-ID validation;
- plain-text preview with approved footer and correlation headers;
- a visible correspondence or acknowledgment link;
- minimal append-only auditing without message-body storage;
- clear blocked conditions before submission;
- later reconciliation of provider events, bounces, acknowledgments, and replies.

## Admin experience

The admin page is at `src/web/outbound-mail/index.html`. It works without live credentials and remains in preview mode until activation.

The workspace shows:

1. **Setup** — provider state, canonical internal mailboxes, system sender, and available identity profiles.
2. **Compose** — original inbound recipient, optional approved fallback, recipients, subject, body, and system-generated mode.
3. **Controls** — footer, visible action-link, retention, and privacy settings.
4. **Preview** — selected sender, Reply-To, selection reason, replacement status, final message, and headers.
5. **Activity** — correspondence events and selected sender identity.

The browser does not submit a free-form `from_address`. The server remains the authority for sender selection.

## Gateway architecture

```text
WW.CX admin / ChatGPT workflow / internal application
        |
        v
Authenticated submission API
        |-- load shared identity registry
        |-- reject or replace arbitrary From and Reply-To
        |-- select identity from system flag, original recipient, or approved hint
        |-- validate recipients, message class, and policy
        |-- assign control ID and opaque action token
        |-- render footer and correlation headers
        |-- verify selected identity is live-authorized
        |-- create minimal audit event
        `-- submit through approved adapter
                 |-- provider API
                 `-- authenticated SMTP smarthost
```

The provider boundary remains abstract so message-policy and identity behavior do not depend on one vendor.

## Transparency rules

The product may record submission, provider delivery events, bounces, explicit acknowledgments, replies, and disclosed action-link access. It must not claim that an email was read merely because a resource was requested.

The policy rejects hidden open-tracking pixels, device fingerprinting, full-IP storage, raw action-token logging, message-body copying into the audit ledger, silent footer injection after signing, and claims that a footer creates legal rights by itself.

## Correlation model

Each message may carry pre-signing headers such as:

```text
X-WWCX-Control-ID: WWCX-20260801T032400Z-0123456789AB
X-WWCX-Case-ID: ENT-184366738
X-WWCX-Action-ID: ENT-ACT-014
X-WWCX-Policy: wwcx.outbound-mail-policy.v1
X-WWCX-Tracking: disclosed-action-link; no-hidden-pixel
```

The restricted audit event records the selected sender address and the selection reason, but not the message body or raw action token.

## ChatGPT and automation path

ChatGPT-assisted sending uses the same submission API as the admin interface. Structured requests should provide the original inbound identity when replying:

```json
{
  "original_recipient": "john@spiritcreekgardens.com",
  "message_class": "business_correspondence",
  "to": ["records@example.com"],
  "cc": [],
  "subject": "Records request",
  "body": "...",
  "case_id": "ENT-184366738",
  "action_id": "ENT-ACT-014",
  "idempotency_key": "provider-independent-request-id"
}
```

For an automated notification that must not invite a reply:

```json
{
  "system_generated": true,
  "to": ["recipient@example.com"],
  "subject": "Automated status notice",
  "body": "..."
}
```

Callers do not need permission to choose arbitrary RFC sender headers. The gateway returns a preview containing its authoritative sender decision.

## Delivery adapters

Adapters should implement a common contract:

- `validate_configuration()`
- `preview_message()`
- `submit_message()`
- `poll_or_receive_delivery_events()`
- `normalize_provider_event()`
- `health()`

The first adapter can wrap an approved Gmail or provider API. A future SMTP adapter can accept authenticated submissions from approved clients, but must not become an open relay.

## Production gates

Before enabling delivery:

1. provision and protect `john-inbox@ww.cx` and `maildesk@ww.cx` at the selected provider;
2. verify each intended sender identity with the outbound provider;
3. configure aligned envelope senders and review SPF, DKIM, and DMARC for every sending domain;
4. add only verified addresses to the live sender allowlist;
5. keep `noreply@ww.cx` restricted to system-generated mail and define bounce handling;
6. configure the correct mailing address and privacy page;
7. store provider credentials outside Git and test key rotation;
8. validate multipart rendering, attachments, idempotency, and duplicate prevention;
9. test audit retention, access controls, export, and deletion routines;
10. run controlled sends only to organization-owned addresses;
11. obtain explicit authorization for live provider and DNS cutover.

Until those gates are completed, previews are permitted but live delivery remains blocked.
