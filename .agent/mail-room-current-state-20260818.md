# Mail Room verified repository state — 2026-08-18

## Authoritative checkpoint

Repository: `johnkaminski727-alt/edge1-management-interface`

Verified feature-complete checkpoint before this documentation branch: `main` = `50f5ef6273fa7ac2e7f0579e76578d9e1e08ad16`.

This is a repository/integration-readiness checkpoint, not production verification.

## Merged Mail Room sequence

- PR #362 — catch-all inbound and staged AI/threat policy — merge `75539c9c97e29a25127aef21b58166bdaf3a97a9`.
- PR #364 — preparation-only catch-all reply identity proposals — merge `43c00e4fd6792ee783ee4542226ad54149b23a34`.
- PR #365 — explicit correspondence/thread correlation — merge `00640677a2a0b9d010079394ff1f8a137c84db59`.
- PR #366 — disabled fail-closed automatic-reply eligibility — merge `f57478fc7f9a7174ff9c6ccefcfda627b734fb53`.
- PR #367 — exact-byte final outbound scan boundary and threading-preserving send path — merge `e57cbb8a5533b4bf8d03daef7230ecd3570f0f99`.
- PR #368 — executable threat decisions and sanitized quarantine/release contracts — merge `a606f8f171da3de63b564512eb7c0aaba92710df`.
- PR #369 — configuration-driven domains and cross-registry drift validation — merge `50f5ef6273fa7ac2e7f0579e76578d9e1e08ad16`.

## Implemented repository capabilities

- Configured managed-domain catch-all inbound routing with exact original-recipient preservation and explicit private/role precedence.
- Server-authoritative sender selection; internal delivery mailboxes are not public identities.
- Preparation-only proposals for previously unseen managed-domain recipients; proposals cannot become live senders through that path.
- Explicit provider-neutral correspondence/thread metadata with validated WW.CX IDs, RFC `Message-ID`/`In-Reply-To`/`References`, and provider correlation IDs; ambiguous heuristic fallback is not used.
- Provider-neutral delivery-event/suppression foundation with durable SQLite state, source verification, idempotency/conflict handling, and minimized event content.
- Disabled fail-closed automatic-reply eligibility with high-consequence message classes blocked by default.
- Exact-byte final outbound MIME scan contract after policy/thread composition and before provider submission. Missing/non-clean/mismatched scan evidence blocks submission.
- Provider-neutral executable threat decisions; required scanning fails closed and AI may escalate risk but cannot weaken hard controls.
- Sanitized quarantine metadata and release-eligibility gates; no automatic or AI release authority.
- Canonical domain source is `config/messaging/mail-identities.json`; inbound, outbound, provider inventory, routes, sender mappings, and internal addresses are cross-validated. DNS inventory derives domains from configuration instead of source-code constants.

## Disabled / not production-verified

- Inbound production routing remains unauthorized.
- Outbound gateway, provider delivery, and live sender allow-list remain disabled in committed configuration.
- Automatic replies remain disabled and prepare-only by default.
- No final scanner runtime is connected by the HTTP gateway; this intentionally blocks secure send activation until an approved scanner adapter exists.
- Antivirus/YARA/reputation/phishing/BEC/sandbox integrations are contracts/policy foundations, not proven production engines.
- Quarantine storage/review/release operator UI and a privileged release operation are not activated.
- Gmail/API/webhook live outbound adapters are not installed; SMTP remains subject to all activation gates and credentials.
- Provider-side mailbox/alias/forwarder provisioning is not fully reconciled.
- MX/SPF/DKIM/DMARC production readiness is incomplete across domains and must not be inferred from repository state.

## Architecture index

Core:
- `server/inbound_mail_hub.py`
- `server/mail_identity_registry.py`
- `server/identity_aware_outbound_gateway.py`
- `server/mail_threading.py`
- `server/mail_auto_reply_policy.py`
- `server/outbound_mail_gateway.py`
- `server/outbound_mail_delivery_events.py`
- `server/mail_final_scan.py`
- `server/mail_secure_submission.py`
- `server/mail_threat_decision.py`
- `server/mail_quarantine.py`
- `server/mail_config_consistency.py`

Canonical/staged configuration:
- `config/messaging/mail-identities.json`
- `config/messaging/inbound-mail-hub.json`
- `config/messaging/outbound-mail-policy.json`
- `config/messaging/mail-threat-policy.json`
- `config/messaging/mail-provider-inventory.json`

Read-only/domain tooling:
- `tools/messaging/mail_domain_inventory.py`

Operator documentation:
- `docs/messaging/`
- `docs/messaging-operations/`

Validation:
- Mail Room-focused workflows under `.github/workflows/` plus repository-wide validation and Edge1 Operator Validation.

## Durable decisions

1. Catch-all inbound identity preservation does not grant outbound authority.
2. Private/shared delivery mailboxes are plumbing and cannot become public senders by convenience.
3. Server policy controls From/Reply-To/control headers/footer/compliance composition.
4. Explicit thread evidence wins; ambiguity blocks automation rather than guessing.
5. Final outbound scanning covers the exact bytes submitted to the provider.
6. Required scanner failure is fail-closed.
7. AI may add risk but may not weaken hard security, alter authorization, or release quarantine.
8. Auto-reply remains prepare-only/disabled until every independent eligibility and production gate is satisfied.
9. The identity registry is the canonical configured domain set; drift across other registries is a CI failure.
10. Implementation readiness and production/provider activation are separate states.
