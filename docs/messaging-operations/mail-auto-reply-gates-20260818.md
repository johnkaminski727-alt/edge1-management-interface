# Mail Room automatic-reply gates — 2026-08-18

Automatic replies remain disabled by default. `config/messaging/mail-auto-reply-policy.json` and `server/mail_auto_reply_policy.py` define a fail-closed eligibility contract only; they do not send or queue mail.

Eligibility requires every configured gate: clean security disposition, acceptable phishing/BEC risk, confident sender and thread identity, live-authorized outbound sender, resolved footer profile, an explicitly allowlisted message class, idempotency success, clean final outbound scan, domain/identity/workflow policy approval, and no human-review requirement.

High-consequence classes remain blocked, including legal/regulatory notices, complaints, security incidents, payment/banking changes, credential/access requests, suspicious invoices, contracts/terms, termination/cancellation, and identity/security events.

The committed policy has `enabled: false`, `automatic_transmission_authorized: false`, `default_mode: prepare_only`, and an empty auto-send allowlist. The evaluator always reports `automatic_transmission_attempted: false`.

Production activation requires a separate authorized change after the upstream security, identity, threading, compliance, provider and final outbound malware gates are operational and evidenced.
