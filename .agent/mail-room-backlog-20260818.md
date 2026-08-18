# Mail Room remaining blockers and backlog — 2026-08-18

## Privileged / external blockers

These must not be performed autonomously under the current authority.

### Provider and mailbox reconciliation

Blocked: verify/export actual provider-side mailbox, alias, forwarding, and sender-verification state for every managed domain; provision anything missing.

Requires: provider account access and potentially external production state changes.

Smallest future operator action: obtain a read-only provider inventory/export first. If changes are then needed, authorize the exact provisioning action separately.

Evidence afterward: timestamped sanitized provider inventory, affected identity/domain, before/after state, and no secret values.

### Final scanner runtime

Blocked: connect an approved server-side scanner adapter to the final outbound scan boundary and inbound threat pipeline.

Requires: runtime/service selection and configuration; ClamAV/clamd, YARA, or other engine installation/operation may affect production services.

Smallest future operator action: select/approve the runtime scanner and authorize installation/configuration on the intended host. Do not enable mail transmission merely by installing the scanner.

Evidence afterward: engine/ruleset versions, bounded test vectors, clean/infected/unscannable/error results, fail-closed verification, service health, and rollback method.

### Production DNS and domain alignment

Blocked: MX/SPF/DKIM/DMARC changes, domain verification/alignment, and live acceptance routing.

Requires: DNS/provider privileges and production traffic decisions.

Smallest future operator action: choose one domain/provider activation target and authorize the exact DNS/provider changes after reviewing the production activation checklist.

Evidence afterward: authoritative DNS observations from independent resolvers, provider verification state, alignment tests, rollback values, and timestamped acceptance results.

### Live outbound provider activation

Blocked: credentials, sender verification, provider adapter activation, and production test transmission.

Requires: provider credentials and explicit authorization for production email transmission.

Smallest future operator action: approve a specific provider/identity test and provide/locate credentials through the approved secret mechanism. Never commit credential values.

Evidence afterward: provider message ID/hash, sender alignment, final-scan evidence, delivery event correlation, bounded audit record, and recipient-confirmed result.

### Live inbound cutover

Blocked: production webhook/local-MTA/provider routing, mailbox delivery, and real-message acceptance tests.

Requires: provider/routing credentials and explicit live inbound authorization.

Smallest future operator action: approve one bounded inbound acceptance test after provider inventory and threat scanner runtime are ready.

Evidence afterward: exact original envelope recipient, route decision, message/correspondence IDs, threat disposition, destination, and no raw-content leakage in general audit logs.

### Quarantine operations

Blocked: durable quarantine storage/runtime integration, privileged release execution, and destructive retention/deletion policy.

Requires: operational/security policy and explicit authorization for any release/deletion with external consequences.

Smallest future operator action: approve a quarantine storage/review design and operator role model; keep release/delete disabled during initial deployment.

Evidence afterward: creation/review/release audit, rescanning result, operator identity, destination validation, rollback/retention evidence.

## Safe future repository enhancements

These are not required to preserve the current checkpoint, but remain sensible future engineering:

- Build a unified persistent correspondence/message ledger that composes the existing threading, delivery-event, quarantine, case/action/control ID contracts without duplicating those subsystems.
- Add concrete inbound scanner adapters after a runtime scanner is selected; normalized decision logic already exists.
- Add operator lookup/API surfaces for correspondence and quarantine metadata with least privilege and no raw hostile-content rendering.
- Add explicit provider adapters only when a provider is selected; keep provider-neutral contracts authoritative.
- Strengthen domain lifecycle administration into a staged candidate/diff/apply model while preserving historical provider evidence on retirement.
- Integrate delivery-event/bounce correlation into the unified correspondence ledger once that ledger exists.
- Add bounded attachment metadata/MIME/archive limit contracts if the inbound parser begins retaining attachment metadata.
- Expand compliance/profile resolution beyond the current server-authoritative outbound policy once legally approved wording/profile variants exist.

## Do not regress

- Do not turn catch-all proposals into live senders automatically.
- Do not expose `john-inbox@ww.cx` or `maildesk@ww.cx` as public send identities.
- Do not reintroduce heuristic ambiguous thread matching for automation.
- Do not allow scanner error/unavailability to become permissive.
- Do not allow AI output or message content to change authorization, weaken hard risk, or release quarantine.
- Do not enable auto-reply or provider transmission merely because repository CI is green.
