# Carrier activation checklist

This checklist is a release gate, not an activation instruction. A checked software foundation does not authorize a carrier, public webhook, DID, billing, credentials, or live traffic.

## Repository-confirmed foundations

- [x] PostgreSQL-backed provider-event idempotency and durable message storage
- [x] Atomic durable outbound queue with concurrency-safe claiming
- [x] Global pause and suppression enforcement before provider submission
- [x] Durable STOP / START / HELP state and audit history
- [x] Fail-closed MMS quarantine foundation; unsupported outbound MMS remains quarantined
- [x] Sender authorization, destination-prefix restrictions, text/recipient bounds, and durable hourly/daily volume reservations
- [x] Provider-neutral webhook and outbound adapter boundary
- [x] Adapter provider-identity and inbound/outbound direction invariants
- [x] Simulator-only integration path with real-carrier adapters absent
- [x] Worker disabled by default and bounded to one-shot execution

## Safe pre-carrier work still required

- [ ] Durable webhook-receipt ledger/queue distinct from normalized message storage, including processing state and replay evidence
- [ ] Real-provider adapter implementations with provider-specific signature freshness/replay verification, kept unregistered and credential-free until separately authorized
- [ ] Delivery/status callback model and idempotent reconciliation for provider delivery events
- [ ] Outbound actor/provenance authorization suitable for a future non-simulator enqueue surface
- [ ] Provider-neutral operational metrics/alerts for receipt, queue, retry, blocked, suppressed, quarantined, and uncertain outcomes
- [ ] Private Edge1 staging acceptance of migrations, disabled worker, read-only management surfaces, backup, restore, and rollback

## Carrier/production authorization gates

Do not cross these gates without separate explicit authorization and the required external information:

- [ ] Select and activate a carrier account or paid service
- [ ] Provision carrier credentials or secrets through an approved secret-management path
- [ ] Purchase/assign/port a DID or messaging sender
- [ ] Establish carrier-specific pricing before setting a meaningful monetary spend ceiling; do not invent a dollar limit
- [ ] Configure or expose a public webhook, including WAF/TLS/DNS/firewall work
- [ ] Make authentication/security-policy changes needed for production actors
- [ ] Perform one approved non-production DID end-to-end test
- [ ] Authorize production SMS/MMS traffic or traffic cutover

## Final release evidence

Before any carrier activation, preserve exact-head CI, private staging evidence, provider-specific replay/signature tests, backup/restore evidence, rollback evidence, and an explicit authorization record for every carrier/production gate crossed.
