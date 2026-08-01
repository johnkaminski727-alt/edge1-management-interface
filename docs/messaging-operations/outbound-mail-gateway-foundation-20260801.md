# WW.CX Outbound Mail Gateway Foundation — 2026-08-01

## Status

Implemented on feature branch as a disabled, provider-neutral foundation. The admin console and controlled preview path are designed for local authenticated use. External delivery, public correspondence-action routes, SMTP cutover, DNS changes and production deployment are not activated.

## Operator experience

The admin console is served at `/outbound-mail/` by the localhost service and provides:

- a guided correspondence form;
- To, Cc and Bcc fields;
- message classification for business, legal/records and commercial messages;
- matter, action and correspondence-control identifiers;
- automatic controlled signature and footer generation;
- a disclosed correspondence-record or acknowledgment link;
- a rendered delivery preview;
- an activation checklist;
- provider readiness cards;
- a privacy and compliance control summary;
- an audit and action matrix that excludes message bodies and raw tokens;
- a send control that stays disabled unless every activation gate is true.

The console is responsive and can be embedded or linked from the authenticated WW.CX operations area. It does not use browser local storage for drafts.

## Gateway boundaries

The implementation separates four responsibilities:

1. **Policy** — controls organization identity, footer contents, disclosure, data minimization, retention and prohibited tracking methods.
2. **Composition** — normalizes recipients, generates an opaque action token, appends the footer, and creates non-sensitive control headers.
3. **Submission** — sends the completed MIME message through a selected provider only after all independent gates pass.
4. **Audit** — records controlled metadata, hashes and provider outcomes without copying the message body or raw action token into the audit stream.

The gateway is a submission service, not an unrestricted open relay. It accepts structured, authenticated application requests and constructs the final message before passing it to an approved provider.

## Provider abstraction

The committed provider profiles reserve stable integration points for:

- authenticated SMTP submission;
- Gmail API or connector-based submission;
- an internal signed webhook to another mail service;
- a disabled provider used by default.

Only the SMTP adapter currently has a live implementation, and it cannot execute while the committed configuration and policy remain disabled. SMTP credentials are referenced only by environment-variable names. No credential values are stored in the repository or returned by the status API.

The Gmail and webhook profiles are contracts for future adapters. They intentionally fail closed until an adapter is installed and tested.

## Messages sent from ChatGPT or other WW.CX tools

A future authenticated tool can call the same gateway API rather than sending mail directly:

```text
ChatGPT or WW.CX workflow
  -> create structured message request
  -> POST /outbound-mail/preview
  -> operator or workflow reviews generated output
  -> explicit authorized POST /outbound-mail/send
  -> selected provider
  -> provider result and controlled audit event
```

This preserves one footer, disclosure and audit policy regardless of whether the initiating client is the admin console, an internal workflow, a Gmail integration or another WW.CX service.

The send endpoint requires a per-request `confirm_send: true` value in addition to server-side activation. A client cannot enable the gateway by changing request data.

## Tracking interpretation

The action URL is visible and its logging purpose is disclosed in the footer. The system may eventually record:

- action-page access;
- an explicit receipt acknowledgment;
- authentication or email verification performed on the action page;
- a controlled document download;
- provider acceptance or rejection;
- delivery-status webhooks from a configured provider.

The following claims are prohibited without independent evidence:

- that the recipient personally read the email;
- that a different IP address proves forwarding;
- that a person is a forwardee based on network or browser metadata;
- that an automated security scanner is a human reader.

Hidden pixels, device fingerprinting and full-IP storage are rejected by policy. The current action endpoint itself is not yet implemented or publicly routed; only unique action URLs are generated during preview.

## Footer design

The footer is professional and formal, but it does not pretend to create legal rights. It contains:

- signer name and role;
- operating and legal entity names;
- mailing and contact information;
- correspondence-control identifier;
- visible action or acknowledgment link;
- logging disclosure and privacy link;
- confidentiality and records notice;
- an express caveat that the notice does not create privilege, confidentiality, contractual duties or other rights that do not otherwise exist;
- an unsubscribe or preference link when the message is classified as commercial.

This avoids misleading recipients while providing consistent records-management language.

## Data handling

The committed gateway configuration provides:

- no persisted message bodies;
- no persisted attachment bytes;
- no raw action tokens in audit events;
- hashed action tokens for correlation and revocation;
- hashed subjects in composition audit records;
- provider status that never exposes runtime credentials;
- JSONL delivery events only after a successful submission.

A later draft-storage feature must select an encrypted content store, define access control and retention, and receive a separate production decision.

## Current API

```text
GET  /outbound-mail/                 Admin console
GET  /outbound-mail/healthz          Local service health
GET  /outbound-mail/status           Activation and provider status
GET  /outbound-mail/audit?limit=50   Controlled audit metadata
POST /outbound-mail/preview          Generate a controlled preview
POST /outbound-mail/send             Gated external submission
```

The server refuses a non-loopback bind. Production access should be provided only through an authenticated reverse proxy with authorization, CSRF protection, bounded request limits and operator audit identity.

## Activation gates

External delivery requires all of the following:

1. gateway `enabled`;
2. deployment authorized;
3. external delivery authorized;
4. send endpoint enabled;
5. outbound-mail policy enabled;
6. policy SMTP cutover authorized;
7. a selected and enabled non-disabled provider;
8. complete runtime provider secrets;
9. an explicit send confirmation on the request;
10. authenticated and authorized access through the WW.CX operations boundary.

The committed repository intentionally fails these gates.

## Production work still required

- Select the first provider and verify its contractual and technical requirements.
- Create runtime secret files or a supported secret-manager integration.
- Determine the sending domain and envelope sender.
- Configure and verify SPF, DKIM and DMARC.
- Design bounce and complaint ingestion.
- Implement the public correspondence-action service and privacy notice.
- Classify automated link scanners separately from human actions.
- Add authenticated WW.CX operations routing and CSRF protection.
- Complete abuse, rate-limit, header-injection, attachment and deliverability testing.
- Establish retention and access-request procedures.
- Perform controlled pilot sends to WW.CX-owned test inboxes.
- Obtain explicit production cutover approval.

## Validation

`tests/validate_outbound_mail_gateway.py` validates the disabled state, policy restrictions, provider-neutral configuration, preview generation, footer disclosure, UI routes, send-button gate and the unit-test suites. Repository CI also compiles the Python files.
