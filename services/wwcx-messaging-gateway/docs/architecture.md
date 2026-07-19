# Architecture

The gateway is a standalone application boundary between messaging carriers and WW.CX applications. Asterisk remains responsible for voice and is not exposed to carrier webhook traffic.

## Initial flow

1. A simulator submits a normalized event to an authenticated internal endpoint.
2. The gateway validates the schema and deduplicates on `(provider, provider_event_id)`.
3. The event is accepted for later asynchronous processing.

## Production evolution

Replace the in-memory store with PostgreSQL, add a durable queue, implement provider signature verification, quarantine MMS media, and place a reverse proxy/WAF in front of public webhook endpoints.
