# Carrier activation checklist

This checklist is a release gate, not an activation instruction. A checked software foundation does not authorize a carrier, public webhook, DID, billing, credentials, security-policy change, or live traffic.

## Repository-confirmed carrier-neutral foundations

- [x] PostgreSQL-backed provider-event idempotency and durable message storage
- [x] Atomic durable outbound queue with concurrency-safe claiming
- [x] Global pause and suppression enforcement before provider submission
- [x] Durable STOP / START / HELP state and audit history
- [x] Fail-closed MMS quarantine foundation; unsupported outbound MMS remains quarantined
- [x] Sender authorization, destination-prefix restrictions, text/recipient bounds, and durable hourly/daily volume reservations
- [x] Provider-neutral webhook and outbound adapter boundary
- [x] Adapter provider-identity and inbound/outbound direction invariants
- [x] Durable verified webhook receipt ledger distinct from message storage
- [x] Recoverable inbound receipt processing with concurrency-safe bounded claiming/retry
- [x] Replay evidence plus same-event-ID changed-body collision rejection
- [x] Bounded durable webhook boundary counters for verification failures, unknown providers, pauses, accepted callbacks, duplicates, and payload conflicts
- [x] Provider-neutral asynchronous delivery/status callback model
- [x] Idempotent and out-of-order-safe delivery-state reconciliation
- [x] Outcome-uncertain provider send failures fail closed for reconciliation instead of blind retry
- [x] Simulator-only integration path with real-carrier adapters absent
- [x] Inbound, outbound, and delivery recovery workers disabled by default and bounded to one-shot execution
- [x] Read-only management evidence for queue, compliance/suppression, verified receipts, webhook boundary audit, and delivery state
- [x] Private staging and backup-first rollback runbook
- [x] Exact-head CI exercises unit tests, repository validation, PostgreSQL integration smoke, outbound queue/compliance policy, durable inbound recovery, webhook collision/audit, and delivery reconciliation

## Remaining readiness work that depends on an external or separately authorized boundary

- [ ] **Live private Edge1 acceptance:** apply/verify migrations and disabled-worker/read-only surfaces on Edge1, capture backup/restore/rollback evidence, and reconcile live service/listener/config state. This is not repository-confirmed until live Edge1 tools are available.
- [ ] **Carrier selection and adapter:** after a provider is selected, implement that provider's adapter unregistered and credential-free first; independently test its signature authentication, timestamp freshness/replay window, payload mapping, send semantics, and delivery-status mapping before any activation.
- [ ] **Production actor/provenance binding:** bind any future non-simulator enqueue surface to an approved authenticated principal and durable actor/request provenance. The current simulator token is intentionally not promoted into a production identity scheme; changing authentication/security policy requires separate authorization.
- [ ] **Monetary spend ceiling:** establish carrier-specific message/media pricing before choosing a meaningful monetary limit. Existing durable hourly/daily volume ceilings remain the pre-carrier safeguard; do not invent a dollar limit without pricing.
- [ ] **Operational alert delivery:** wire the repository-confirmed read-only counters/state into the approved private monitoring/alert destination during live staging. Do not create an external notification path without its separate operational authorization.

## Carrier/production authorization gates

Do not cross these gates without separate explicit authorization and the required external information:

- [ ] Select and activate a carrier account or paid service
- [ ] Provision carrier credentials or secrets through an approved secret-management path
- [ ] Purchase/assign/port a DID or messaging sender
- [ ] Configure or expose a public webhook, including WAF/TLS/DNS/firewall work
- [ ] Make authentication/security-policy changes needed for production actors
- [ ] Make certificate or public listener changes
- [ ] Change production Asterisk/FreePBX routing
- [ ] Perform one approved non-production DID end-to-end carrier test
- [ ] Authorize production SMS/MMS traffic or traffic cutover

## Final release evidence

Before any carrier activation, preserve the exact repository revision and exact-head CI, live private staging evidence, provider-specific replay/signature tests, backup/restore evidence, rollback evidence, production actor/provenance design approval, carrier pricing/spend-limit evidence, and an explicit authorization record for every carrier/production gate crossed.
