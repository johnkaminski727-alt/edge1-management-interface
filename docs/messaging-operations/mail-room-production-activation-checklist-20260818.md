# Mail Room production activation checklist — 2026-08-18

This checklist distinguishes repository implementation readiness from privileged production activation. Checking an item does not itself authorize the action.

## Provider and identity readiness

- [ ] Select the production inbound/outbound provider(s).
- [ ] Capture a fresh read-only provider mailbox/alias/forwarder inventory.
- [ ] Reconcile provider inventory with `mail-identities.json` and inbound routes.
- [ ] Verify intended public sender identities; keep internal delivery mailboxes non-public.
- [ ] Verify catch-all behavior does not grant send authority.
- [ ] Establish approved secret/credential locations without committing values.

## Domain and DNS readiness

- [ ] Verify authoritative nameservers for each activation target.
- [ ] Verify or change MX only with explicit authorization and rollback values recorded.
- [ ] Verify SPF alignment.
- [ ] Verify DKIM selectors/signing and key custody.
- [ ] Verify DMARC policy/reporting and organizational alignment.
- [ ] Verify provider/domain ownership state.
- [ ] Re-run read-only DNS inventory from independent resolvers after any change.

## Threat and quarantine readiness

- [ ] Select and approve the required scanner runtime.
- [ ] Connect inbound scanning adapters to normalized threat decisions.
- [ ] Connect final outbound MIME scanning to the secure submission boundary.
- [ ] Prove `clean`, `infected`, `suspicious`, `unscannable`, `scan_error`, and `not_scanned` behavior.
- [ ] Prove required scanner failure remains fail-closed.
- [ ] Configure bounded archive recursion/type verification/active-content handling.
- [ ] Configure URL/QR extraction and reputation sources only after approval.
- [ ] Establish quarantine storage, operator review access, retention, backup, and audit.
- [ ] Keep quarantine release and deletion disabled until separately authorized and tested.
- [ ] Prove AI cannot weaken hard blocks, alter authorization, or release quarantine.

## Outbound readiness

- [ ] Select/install the concrete provider adapter.
- [ ] Verify sender authorization and domain alignment.
- [ ] Verify server-authoritative From/Reply-To/control headers/footer composition.
- [ ] Verify threading headers survive into final provider-bound MIME.
- [ ] Verify the exact provider-bound bytes are final-scanned clean.
- [ ] Verify provider submission cannot occur without all gateway/policy/identity/scan gates.
- [ ] Verify delivery event/bounce/complaint correlation and idempotency.
- [ ] Keep automatic replies disabled during initial provider testing.

## Inbound readiness

- [ ] Select/install concrete ingress adapter.
- [ ] Verify source authentication/anti-replay for provider webhook or local MTA ingress.
- [ ] Verify arbitrary local-part acceptance for managed-domain catch-all.
- [ ] Verify unmanaged-domain rejection.
- [ ] Verify private route precedence and exact original-recipient preservation.
- [ ] Verify message/body/attachment retention limits and inert handling.
- [ ] Verify threat disposition routes clean mail and quarantines blocked/unknown-required states.

## Auto-reply readiness

- [ ] Keep committed mode prepare-only until a separate activation decision.
- [ ] Revalidate all security, identity, threading, sender, compliance, idempotency, final-scan, workflow, and human-review gates.
- [ ] Verify high-consequence classes remain blocked: legal/regulatory, complaints, security incidents, financial/banking changes, credentials/access, contracts/terms, cancellation/termination, and equivalent matters.
- [ ] Verify thread ambiguity blocks automation.
- [ ] Verify duplicate/idempotency protection across retries and provider events.
- [ ] Obtain explicit authorization before any production automatic reply is enabled.

## Operations and rollback

- [ ] Define monitoring/alerting and service health checks.
- [ ] Define backups for correspondence/delivery/quarantine operational state.
- [ ] Define provider/DNS/service rollback steps before cutover.
- [ ] Capture before/after configuration evidence for every privileged change.
- [ ] Perform bounded live inbound test only with explicit authorization.
- [ ] Perform bounded live outbound test only with explicit authorization.
- [ ] Reconcile thread/reply/delivery event end-to-end.
- [ ] Complete final security review and record production verification separately from repository CI.
