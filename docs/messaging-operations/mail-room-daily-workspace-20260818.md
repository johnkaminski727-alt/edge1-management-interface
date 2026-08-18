# WW.CX Mail Room daily workspace — 2026-08-18

## Purpose

The Mail Room interface is a daily-use product, not a thin administrative skin over the mail gateway. Its job is to make important correspondence calm, fast, understandable, and difficult to misuse while keeping the security and identity machinery available when it is actually needed.

## Experience principles

1. **Write first.** The primary action is “Write a message,” not gateway setup.
2. **Keep the everyday path short.** The normal path is Today → Compose → Review. Safety & privacy and system readiness remain inspectable without becoming routine chores.
3. **Use server-authoritative defaults.** Sender identity, provider readiness, security controls, policy footers, and live-delivery gates come from the server. The UI must not pretend a local checkbox changes a server policy when it does not.
4. **Explain blocks in plain language.** Errors say what needs attention; disabled production features are described as safe-mode behavior rather than mysterious failures.
5. **Preserve catch-all identity safely.** An unseen recipient on a managed catch-all domain may be preserved for preview, matching the backend behavior, while remaining unauthorized for live sending until separately approved.
6. **Do not hide important safety state.** Preview-only/live mode remains visible at the top of the workspace and the send button remains disabled until all server gates are satisfied.
7. **Keep technical detail available, not dominant.** Headers, provider state, mailboxes, managed domains, and activation checks live behind intentional detail views.
8. **Respect draft privacy.** The browser UI does not save message bodies to local browser storage.
9. **Support repeated daily use.** Keyboard shortcuts cover compose, activity search, return to Today, and review generation; responsive layouts support smaller screens.
10. **Accessibility is part of usability.** The interface includes a skip link, focus management between views, live status regions, keyboard operation, responsive layouts, and reduced-motion support.

## Implemented in this increment

- Renamed and repositioned the console as **WW.CX Mail Room**.
- Added a Today home view with one-click compose and a concise readiness summary.
- Reduced the ordinary correspondence path so Compose can generate Review directly.
- Moved identity/case/special-purpose fields behind Message context.
- Moved technical gateway/provider/mailbox checks behind System readiness.
- Converted privacy/tracking controls that are server policy into read-only policy indicators instead of misleading local switches.
- Added plain-language sender-selection explanations.
- Added managed-domain status to the identity-aware gateway status payload.
- Updated frontend validation so managed-domain catch-all addresses are previewable rather than incorrectly rejected.
- Added keyboard shortcuts, focus handling, toast feedback, activity count, responsive layout, and reduced-motion behavior.
- Kept live delivery disabled by existing server/configuration gates; this change does not activate a provider, sender, scanner, DNS record, or production route.

## Deliberately not claimed complete

This increment makes the existing outbound correspondence workspace materially easier to use. It does **not** yet create the complete two-way Mail Room experience.

Still required for the full daily Mail Room:

- real Inbox and assignment views backed by an operator-safe inbound message API;
- conversation/thread view using the existing correspondence and RFC threading metadata;
- quarantine review UI backed by sanitized quarantine records and privileged release controls;
- delivery-health presentation for bounce, complaint, unsubscribe, suppression, and provider events;
- domains and identities administration with provider/DNS readiness evidence;
- persistent correspondence ledger tying thread, control, case, provider, delivery, and quarantine evidence together;
- usability testing against real daily workflows once the relevant backend APIs exist.

## Safety boundary

No production mail was sent. No DNS, mailbox, provider routing, sender authorization, credentials, scanner runtime, quarantine release, or live ingress/egress setting is changed by this UI increment.
