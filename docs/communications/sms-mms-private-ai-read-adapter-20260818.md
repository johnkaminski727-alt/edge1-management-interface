# SMS/MMS Private AI read adapter

Date: 2026-08-18

## Scope

This repository increment adds bounded read-only SMS/MMS context and local draft preparation for WW.CX AI without sending carrier traffic or granting messaging control authority.

## Gateway read surface

The existing authenticated management-read token now protects:

- `GET /v1/management/status`
- `GET /v1/management/messages/recent?limit=N`
- `GET /v1/management/messages/{event_id}`

Recent reads are bounded to 100 events. Returned message text is capped at 1,000 characters and marked untrusted. Media URLs and verification internals are not returned; only bounded content type and SHA-256 metadata are exposed. Every read response states `mutation_authorized: false`.

The PostgreSQL event store now implements the same `list_recent` and `get_event` read interface already present in the in-memory store.

## BigBird tool facade

`integrations/bigbird_messaging` now exposes:

- `status()`
- `recent_conversations(limit=...)`
- `conversation_event(event_id)`
- `prepare_reply(event_id=..., text=...)`

`prepare_reply` is local artifact preparation only. It returns `state: drafted`, `delivery_status: prepared_not_sent`, `send_authorized: false`, and `mutation_authorized: false`. It does not call a provider endpoint.

The read facade fails closed if the gateway ever returns a read response that does not explicitly preserve `mutation_authorized: false`.

## Capability state

Repository-ready capabilities:

- `messages.status.read`
- `messages.conversation.read`
- `messages.draft.prepare`

Historical/live accepted capabilities remain separately recorded as `communications.read` and `telephony.read`. This change does not claim that the SMS/MMS adapter has been deployed or accepted on Edge1.

## Unchanged boundaries

This increment does not enable `messages.send`, live SMS/MMS traffic, provider credentials, carrier routing, management control, quarantine release, DNS/firewall/certificate/authentication changes, or generic AI execution.

No production SMS/MMS traffic is required for repository acceptance.
