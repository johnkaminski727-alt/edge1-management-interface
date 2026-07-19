# Carrier activation checklist

Do not activate a production carrier until all items are complete:

- PostgreSQL-backed idempotency and audit storage
- Durable outbound and webhook queues
- Provider webhook signature and replay verification
- Secret manager integration
- MMS quarantine, type/size enforcement, and malware scanning
- STOP, START, and HELP workflows
- Consent and suppression records
- Per-number and per-user authorization
- Rate, spend, and destination controls
- Public endpoint WAF, TLS, monitoring, and failover
- Backup restoration and rollback test evidence
- One approved non-production DID end-to-end test
