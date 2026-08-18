# Mail Room durable engineering handoff — 2026-08-18

## Resume point

Use `main` after the archive-readiness PR that contains this file. Before any new work, verify current `main` and reconcile changes made after this checkpoint.

The last feature checkpoint before archive documentation was `50f5ef6273fa7ac2e7f0579e76578d9e1e08ad16` (merge PR #369).

Read first:

1. `.agent/mail-room-current-state-20260818.md`
2. `.agent/mail-room-validation-20260818.md`
3. `.agent/mail-room-backlog-20260818.md`
4. `docs/messaging-operations/mail-room-production-activation-checklist-20260818.md`
5. `docs/messaging-operations/mail-room-archive-manifest-20260818.md`

Then inspect current code/config/tests rather than trusting any stale prose.

## What the system currently does

Repository foundations provide configuration-driven managed domains, catch-all inbound routing rules, exact original-recipient identity preservation, safe sender selection, explicit correspondence/thread metadata, provider-neutral delivery events, disabled auto-reply eligibility, exact-byte final outbound scan gating, normalized threat decisions, sanitized quarantine/release prerequisites, and cross-registry domain consistency validation.

The committed system is intentionally not a production mail service. Production ingress, provider delivery, automatic replies, final scanner runtime integration, DNS cutover, sender activation, and quarantine release remain closed or unverified.

## Most important recent changes

- #367 fixed send-path divergence: identity/thread-aware preview metadata is now carried into a secure submission boundary, and final scanning covers the exact MIME bytes handed to the provider adapter.
- #368 added executable fail-closed threat decisions and quarantine metadata/release prerequisites without adding a scanner engine or release operation.
- #369 made the identity registry the canonical configured domain set, added drift validation, and removed the DNS inventory tool's hard-coded managed-domain list.

## What must not be assumed

- Green repository CI is not production verification.
- A configured identity is not necessarily provider-provisioned.
- A managed domain is not necessarily DNS/mail ready.
- A catch-all reply identity proposal is not authorized to send.
- A scanner contract is not a running scanner engine.
- A quarantine release-eligibility result is not authorization to execute release.
- Provider inventory records are observational and may become stale; re-observe before production decisions.

## Exact next engineering action

If continuing repository-only work without new production authority, the highest-value next feature is a unified persistent correspondence ledger that references—not duplicates—the existing thread, delivery-event, quarantine, case/action/control, and provider-correlation contracts. Design it around deterministic IDs, idempotent event application, minimized content retention, and explicit provenance.

If moving toward production instead, do not start coding around the gates. Follow the production activation checklist and obtain explicit authorization for the first privileged action, preferably beginning with read-only provider/mailbox inventory and scanner-runtime selection.
