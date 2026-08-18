# Mail Room UI experience checkpoint — 2026-08-18

## Product requirement

The Mail Room must be easy enough and pleasant enough to become a trusted, cherished part of daily work. This is a durable product requirement, not optional visual polish.

## Current UI direction

The outbound console is being treated as a daily correspondence workspace rather than a gateway configuration page.

Daily path:

1. Today
2. Compose
3. Review
4. Send only when every production gate is independently satisfied

Safety & privacy and System readiness remain available as inspectable detail views, but should not interrupt routine correspondence.

## Durable design decisions

- Hide infrastructure until it helps answer a user question or resolve a block.
- Do not present server policy as a fake local control.
- Prefer automatic sender selection; explain the chosen identity in plain language.
- Preserve managed-domain catch-all recipients for preview without granting live sending authority.
- Keep live/preview mode unmissable.
- Never persist draft message bodies in browser local storage by default.
- Prefer review-before-send over clever automation.
- Keep keyboard, mobile, focus, and reduced-motion behavior first-class.
- Use plain language in the main workflow; technical headers and provider detail belong behind deliberate disclosure.
- Optimize for repeated daily tasks before adding more administrative surface area.

## Implemented branch

Branch: `agent/mail-room-daily-workspace-20260818`

Material files:

- `src/web/outbound-mail/index.html`
- `src/web/outbound-mail/app.js`
- `src/web/outbound-mail/styles.css`
- `server/identity_aware_outbound_gateway.py`
- `tests/test_outbound_mail_admin_assets.py`
- `tests/test_identity_aware_outbound_gateway.py`
- `docs/messaging-operations/mail-room-daily-workspace-20260818.md`

## Next UI milestones after this increment

1. Inbox / assigned / waiting views backed by sanitized inbound APIs.
2. Conversation timeline using explicit correspondence/thread metadata.
3. Quarantine review surface with no automatic release authority.
4. Delivery health and suppression presentation.
5. Domains & identities readiness screen.
6. Persistent correspondence ledger and case-level search.
7. Real workflow usability passes and iterative friction removal.

## Production boundary

This UI work must not itself enable providers, DNS, live ingress/egress, sender authorization, scanner runtime, credentials, or quarantine release.
