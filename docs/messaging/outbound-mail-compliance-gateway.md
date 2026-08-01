# WW.CX Outbound Mail Compliance Gateway

## Status

Feature-branch foundation only. The committed policy is disabled. No SMTP relay, mailbox setting, DNS record, signing key, production route, or live outbound-message flow has been changed.

Production cutover requires an approved sender identity, a configured mailing address, credentials stored outside the repository, SPF/DKIM/DMARC review, rollback instructions, and explicit authorization at execution time.

## Product goal

Provide one approachable admin workspace for outbound correspondence sent from the WW.CX site, ChatGPT-assisted workflows, internal tools, forms, and later approved SMTP or provider-API clients.

The gateway should make safe defaults easy:

- choose a sender profile and message class;
- enter or import recipients, subject, body, case ID, and action ID;
- preview plain-text and HTML output before sending;
- append a consistent signature and correspondence-control footer;
- generate a visible action or acknowledgment link;
- assign a unique control ID;
- write a minimal audit event without copying the message body;
- show compliance checks and blocked conditions before submission;
- preserve provider message IDs, bounces, acknowledgments, and later responses;
- export a correspondence matrix by case, recipient, status, and action.

## Admin experience

The first admin page is located at `src/web/outbound-mail/index.html`. It is intentionally usable without live credentials and operates in preview mode until a deployment adapter is explicitly enabled.

The workspace is organized into five steps:

1. **Setup** — organization identity, mailing address, privacy URL, delivery provider, and safe defaults.
2. **Compose** — sender, recipients, subject, message class, case ID, action ID, and body.
3. **Controls** — footer components, action-link behavior, retention, and recipient-address logging.
4. **Preview** — final rendered message, headers, control ID, and policy warnings.
5. **Activity** — message matrix covering composed, submitted, delivered, bounced, acknowledged, accessed, replied, and closed events.

## Gateway architecture

```text
WW.CX admin / ChatGPT workflow / internal application / future SMTP client
        |
        v
Authenticated WW.CX submission API
        |-- validate sender, recipient, class, and policy
        |-- assign control ID and opaque action token
        |-- render plain-text and HTML footers
        |-- add X-WWCX correlation headers
        |-- create append-only audit event
        |-- create provider idempotency key
        `-- submit through selected adapter
                 |-- provider API
                 `-- authenticated SMTP smarthost

Visible action link -> https://ww.cx/correspondence/r/<opaque-token>
                         |-- clear logging disclosure
                         |-- correspondence metadata
                         |-- optional verified acknowledgment
                         |-- records upload or response link
                         `-- privacy and retention information
```

The provider boundary remains abstract so the gateway can support a Gmail/API workflow initially and later use a dedicated outbound provider or authenticated smarthost without changing message-policy behavior.

## Transparency rules

The product may record submission, provider delivery events, bounces, explicit acknowledgments, replies, and disclosed action-link access. It must not claim that an email was read merely because a resource was requested.

The policy rejects:

- hidden open-tracking pixels;
- device fingerprinting;
- full-IP storage;
- raw action-token logging;
- message-body copying into the audit ledger;
- silent footer injection after DKIM signing;
- assertions that a footer creates privilege, confidentiality, service, or contractual rights by itself.

Action-link events must be confidence-qualified because corporate link scanners, previews, proxies, VPNs, shared devices, and forwarded messages can produce access events.

## Default footer

```text
--
John Kaminski
Authorized Representative
WW.CX | Christmas Island Worldwide
<configured mailing address>
Email: john@ww.cx | Web: https://ww.cx

[WWCX-CORRESPONDENCE-CONTROL]
Correspondence control: <CONTROL-ID>
View the correspondence record or acknowledge receipt: <VISIBLE-ACTION-URL>
Access to the linked correspondence record may be logged for security,
delivery verification, records management, and dispute resolution.
Privacy information: https://ww.cx/privacy

CONFIDENTIALITY AND RECORDS NOTICE: This message and any attachments may
contain confidential information intended for the addressed recipient. If
received in error, notify the sender and delete the material.
This notice does not create confidentiality, privilege, a contractual duty,
or other legal rights where they do not otherwise exist.
```

Commercial messages additionally require a configured unsubscribe or preference-management link.

## Correlation model

Each message may carry these pre-signing headers:

```text
X-WWCX-Control-ID: WWCX-20260801T032400Z-0123456789AB
X-WWCX-Case-ID: ENT-184366738
X-WWCX-Action-ID: ENT-ACT-014
X-WWCX-Policy: wwcx.outbound-mail-policy.v1
X-WWCX-Tracking: disclosed-action-link; no-hidden-pixel
```

Headers can assist internal reconciliation when preserved but do not prove reading or forwarding. The action matrix should keep evidence types separate and assign confidence explicitly.

## ChatGPT and automation path

ChatGPT-assisted sending should use the same submission API as the admin interface. A future connector call should provide structured fields rather than raw SMTP access:

```json
{
  "sender_profile": "john-wwcx",
  "message_class": "business_correspondence",
  "to": ["records@example.com"],
  "cc": [],
  "subject": "Records request",
  "plain_text_body": "...",
  "case_id": "ENT-184366738",
  "action_id": "ENT-ACT-014",
  "idempotency_key": "provider-independent-request-id"
}
```

The service returns a preview first unless the caller has an explicit send scope. A send response should include the WW.CX control ID, provider message ID, submission timestamp, recipient disposition, and authoritative audit-record location.

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

1. Confirm the legal and operating identity displayed in the footer.
2. Configure the correct mailing address and privacy page.
3. Choose and verify the sending domain and sender profiles.
4. Review SPF, DKIM, DMARC, bounce handling, complaints, and unsubscribe behavior.
5. Store provider credentials outside Git and test key rotation.
6. Validate multipart text/HTML rendering and attachment preservation.
7. Confirm idempotency and duplicate-send prevention.
8. Validate audit retention, access control, export, and deletion routines.
9. Run a controlled test to internal addresses.
10. Obtain explicit authorization for live SMTP/API cutover.
