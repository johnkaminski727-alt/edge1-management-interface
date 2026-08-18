# Durable outbound queue foundation

Status: repository/runtime foundation only. No carrier activation, public webhook exposure, DID assignment, or production message authority is granted by this code.

## Safety gates

Outbound processing is deliberately fail-closed:

- PostgreSQL is required for durable queueing; memory mode cannot enqueue outbound work.
- `WWCX_SIMULATOR_OUTBOUND_ENABLED=false` by default, so the simulator queue endpoint is off unless explicitly enabled for a bounded test.
- `WWCX_OUTBOUND_WORKER_ENABLED=false` by default.
- the worker requires `--once` and processes at most one job per invocation; continuous sending is intentionally not implemented.
- `WWCX_OUTBOUND_PROVIDER_ALLOWLIST` defaults to `simulator`, so a future real carrier adapter does not become send-capable merely because it is registered.
- the existing messaging pause state is checked before claiming a job.
- suppression records are checked before provider submission.
- MMS with media is placed in `quarantined` state because trusted scan/release authority is not yet available.
- provider failures are durably retried with bounded delay/attempt settings and eventually become `failed`.

## Queue lifecycle

`PostgresEventStore.enqueue_outbound()` atomically writes:

1. `messaging_events` with `message.outbound.queued` and the normalized payload;
2. the corresponding `messages` row with status `queued`;
3. an `outbound_jobs` row in `pending` state.

`claim_outbound_job()` uses PostgreSQL `FOR UPDATE ... SKIP LOCKED` so concurrent one-shot workers cannot claim the same ready job. The worker then either:

- marks it `sent` with the provider message ID;
- marks it `suppressed`, `quarantined`, or `blocked` without provider submission; or
- returns it to `pending` with a future `available_at` until the bounded attempt limit is reached, after which it becomes `failed`.

A job left in `processing` after an uncertain provider outcome is intentionally not auto-reclaimed. That fail-closed state requires operator/provider reconciliation before any retry, avoiding accidental duplicate delivery until a real carrier idempotency contract is implemented and verified.

## Development-only simulator flow

With PostgreSQL plus both explicit simulator/worker gates enabled:

```sh
curl -X POST http://127.0.0.1:58080/v1/simulator/outbound \
  -H 'content-type: application/json' \
  -H 'x-wwcx-simulator-token: ...' \
  -d '{..."direction":"outbound","provider":"simulator"...}'

python -m app.outbound_worker --once
```

Queue counts are exposed read-only at `/v1/management/outbound/queue` under the existing management read token.

## Production boundary

Do not schedule or continuously run the worker against a real carrier until the separate production gates are satisfied, including carrier selection/onboarding, credentials, approved DID, real-provider send semantics, webhook verification/replay controls, STOP/START/HELP, authorization, rate/spend/destination controls, and current explicit production/carrier authorization.
