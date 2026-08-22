# Cookie Monster Alpha M3-M5 Control Foundations

Status: source implementation only. No production activation, archive credentialing, or canonical archive mutation is introduced by this milestone.

## M3 - human review queue

`server/cookie_monster_review.py` adds an append-only review decision ledger beside the generated Alpha evidence.

Allowed transitions are deliberately small:

- `draft -> pending_review`
- `pending_review -> approved`
- `pending_review -> rejected`
- `approved` and `rejected` are terminal in Alpha

Knowledge records are not rewritten to record a review decision. Each decision is a new hash-chained `review-decisions.jsonl` event. `review-state.json` is a replaceable derived view for the operator UI.

The human-facing Cookie Monster page now renders review state and operator actions. Because an authenticated web mutation transport has not yet been activated, the controls generate/copy the exact bounded CLI command rather than exposing an unauthenticated approval endpoint.

## Big Bird handoff contract

`server/cookie_monster_contract.py` defines `wwcx.cookie-monster.job.v1`.

The handoff contains a dataset name, requested stages, bounded file/time budgets, actor, deterministic idempotency key and deterministic job ID. It explicitly does not carry a filesystem path, URL, command, token, secret, or credential. Runtime configuration will map approved dataset names to staging sources later.

This fits the existing Big Bird control-plane pattern: Big Bird hands off a bounded intent; Cookie Monster owns ingestion execution and provenance.

## M4 - bounded Fengus worker

`server/cookie_monster_fengus_worker.py` is a data-only worker with an operation allowlist. Alpha operations accept inline bounded data and a content-addressed source ID; they do not accept source paths or archive authority.

`deploy/cookie-monster-fengus-worker@.service` provides the OS boundary for future activation:

- `PrivateNetwork=yes`
- `ProtectSystem=strict`
- `NoNewPrivileges=yes`
- archive/generated-store paths explicitly inaccessible
- only Fengus inbox read and outbox write paths exposed
- memory, CPU, task, file-descriptor and execution-time limits

No credential is required or provisioned for the worker.

## M5 - audit boundary

The ingestion foundation already records every source read plus metadata diagnostics and idempotent record reuse. M3 adds immutable human-decision history. Big Bird job execution/audit integration remains a runtime activation task; the source contract is now defined without giving Big Bird or Fengus direct archive paths.

## Validation

Targeted source validation for this milestone:

```text
python3 -m py_compile server/cookie_monster_contract.py server/cookie_monster_review.py server/cookie_monster_fengus_worker.py tests/test_cookie_monster_control.py
python3 -m unittest -v tests.test_cookie_monster_control
node --check <extracted Cookie Monster inline JavaScript>
systemd-analyze verify deploy/cookie-monster-fengus-worker@.service
```

The test suite covers deterministic/path-free Big Bird jobs, append-only review transitions, terminal approval states, Fengus allowlisting, archive/command rejection, systemd isolation settings, and UI presence for mascot/review/jobs/Fengus.

## Still not activated

- No real archive/staging filesystem has been selected or mounted for Cookie Monster.
- No Fengus system user, directories, service, or credential has been created on Edge1 by this source milestone.
- No web approval mutation endpoint exists yet; that requires the authenticated operator boundary to be selected and wired deliberately.
- No automatic archive modification exists.
