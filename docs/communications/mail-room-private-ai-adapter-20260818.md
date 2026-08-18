# Mail Room Private AI adapter

Date: 2026-08-18

## Repository-ready capabilities

- `mail.status.read`
- `mail.draft.prepare`

`server/mail_ai_adapter.py` reuses the existing identity-aware outbound-mail gateway and policy engine. Status exposes sanitized readiness/identity information. Draft preparation runs the same sender-selection, policy, threading, footer, control-header, and audit preparation logic already used by Mail Room, then strips the raw action token and labels the artifact `prepared_not_sent`.

The adapter performs no network request and does not invoke `send_message`.

## Correspondence read boundary

`mail.correspondence.read` remains intentionally blocked pending an explicitly authorized authoritative native Mail Room correspondence source.

Outbound audit metadata is not treated as if it were an inbox or correspondence archive. The channel-neutral layer must not invent message bodies or thread history from audit records.

## Separation of authority

A prepared AI draft returns:

- `state: drafted`
- `ai_generated: true`
- `delivery_status: prepared_not_sent`
- `network_activity: false`
- `external_delivery_attempted: false`
- `send_authorized: false`
- `mutation_authorized: false`

This repository increment does not enable mail send, provider credentials, live routing, DNS/authentication changes, quarantine release, or any generic AI execution path.

## Acceptance

Repository validation covers the adapter directly through `tests/validate_mail_ai_adapter.py`. Fresh Edge1 deployment and live browser acceptance remain separate evidence and are not claimed by this increment.
