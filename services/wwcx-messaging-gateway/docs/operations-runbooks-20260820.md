# WW.CX Messaging operations runbooks

Date: 2026-08-20

These runbooks are fail-closed. Never solve an incident by enabling live traffic, weakening authentication, bypassing MMS quarantine, retrying an outcome-uncertain send, exposing secrets, or changing DNS/firewall/certificates without the required approval.

## Universal first response

1. Record UTC time, affected service, observed symptom and operator identity.
2. Capture current repository/deployment/runtime provenance before mutation.
3. Check gateway `/healthz`, `/readyz`, management status, service state, listener bindings, PostgreSQL health, queue state, disk and memory.
4. Preserve fresh logs and any message/provider identifiers needed for reconciliation; do not copy message bodies or credentials into tickets unnecessarily.
5. If external delivery safety is uncertain, pause intake/worker activity through the approved control path rather than killing data stores or deleting queue rows.
6. Back up affected runtime/configuration before changing it.
7. Make the smallest reversible correction, verify health and fresh logs, then record evidence and rollback location.

## Provider outage

**Trigger:** carrier API unavailable, elevated 5xx/timeouts, or provider health degraded.

- keep ambiguous in-flight sends in reconciliation-required state;
- do not automatically retry messages whose provider acceptance is unknown;
- leave new outbound sending disabled/paused if duplicate or spend risk exists;
- verify provider status independently and distinguish connection failure from post-submit uncertainty;
- after provider recovery, reconcile provider message IDs/DLRs before releasing any held job;
- resume only after bounded synthetic/private checks pass.

## Webhook verification failure

**Trigger:** signature failures or replay-window rejects rise unexpectedly.

- confirm server UTC/time synchronization before altering any replay window;
- verify the configured provider public verification material without printing it;
- verify reverse-proxy preserves raw request body and required signature/timestamp headers;
- confirm callback URL/provider environment is correct;
- do not disable signature verification as a workaround;
- retain only bounded failure counters for unverified requests, not raw untrusted bodies.

## Stuck outbound queue

**Trigger:** pending/processing jobs age beyond expected worker cadence.

- inspect whether the worker is intentionally disabled;
- check pause state, provider allowlist/registration, policy, suppression and rate-limit state;
- inspect the oldest claimed job and its last provider outcome;
- if acceptance is unknown, reconcile with provider before retry;
- never reset all processing jobs blindly;
- after correction, process at most one bounded job first and verify its durable transition.

## Uncertain send

**Trigger:** worker returns `reconcile_required` / `provider_outcome_unknown`.

- freeze that job in its claimed/processing state;
- capture local job ID, local event ID, sender, destination hash/reference, attempted time and provider context without leaking content;
- query the provider by safe supported identifier/time window once credentials and provider access are authorized;
- if provider proves acceptance, record provider message ID and await/reconcile DLR;
- if provider proves non-acceptance, move through the explicit safe-retry path;
- if outcome cannot be proven, escalate for operator decision; never infer non-delivery from missing DLR alone.

## Database failure

- keep gateway fail-closed if PostgreSQL readiness fails;
- do not switch a production runtime to volatile in-memory storage;
- capture PostgreSQL service/log/disk state and migration provenance;
- restore from the documented backup only after verifying the target and preserving current evidence;
- run migration/readiness checks and bounded persistence/restart acceptance before resuming workers.

## Full disk / capacity pressure

- pause growth-producing work safely;
- identify the filesystem and top consumers without deleting evidence;
- protect PostgreSQL and private quarantine integrity first;
- archive/rotate only data covered by an approved retention policy;
- never delete quarantine blobs independently of metadata/audit state;
- verify free space, database writes, queue durability and service health after remediation.

## MMS malware / scanner failure

**Malicious verdict:** keep attachment `quarantined_malicious`; do not preview, release or copy it to a web-served path.

**Scanner unavailable/error/timeout:** keep the item held in the corresponding fail-closed state; repair scanner availability separately.

**Digest/integrity failure:** treat as security-significant, preserve metadata/audit evidence, and do not rescan altered bytes as though they were the original attachment.

A `clean` verdict remains `scanned_clean_held`; scanner success is not release authorization.

## AI gateway failure

- Messaging Gateway operation remains independent of AI availability;
- disable/degrade copilot features rather than broadening privileges or bypassing policy;
- preserve native message records unchanged;
- drafts/summaries that cannot be provenance-bound must not be persisted as authoritative data;
- after recovery, verify BigBird tool registry, read-only scopes and `send_authorized=false` behavior before restoring copilot UX.

## Carrier credential failure

- do not print, commit, email or paste credential values into logs/issues;
- distinguish missing/invalid credential from provider outage;
- if rotation is required, stop: credential rotation is an explicit authorization boundary;
- after authorized credential repair, run authentication-only/provider-sandbox checks before any live message canary.

## Emergency disable / pause

Use the approved gateway pause/control mechanism when available. Confirm:

- new intake/sends are stopped as intended;
- durable data remains readable;
- no queue rows are destroyed;
- the reason, actor and time are audited;
- resume requires a separate deliberate operator action after the incident condition is cleared.

## Rollback

The last documented Phase 3 private acceptance backup root is:

`/var/backups/wwcx-messaging-gateway/phase3-final-20260819T010540Z`

Before rollback, capture the current runtime/source hash and database/migration state. Prefer the repository's documented installer/rollback path; do not hand-edit a temporary production fix that cannot be reproduced from source. After rollback verify service state, loopback listener, health/readiness, PostgreSQL persistence, queue state, policy disabled/enabled state as intended, fresh logs and absence of unexpected public listeners.

## Post-incident record

Record the trigger, impact window, exact runtime/source versions, relevant sanitized IDs, action taken, validation evidence, rollback location, remaining risk and whether any explicit-approval boundary was reached. Update `.agent/` / handoff records when repository or operating assumptions changed.
