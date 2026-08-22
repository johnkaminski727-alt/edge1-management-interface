# Cookie Monster Alpha Dataset Dispatch

Status: source-ready bounded dispatch foundation; not activated on Edge1.

## Purpose

Big Bird may request Cookie Monster ingestion by a bounded dataset slug, but it must never choose an arbitrary filesystem path, URL, command, credential, or archive location. `server/cookie_monster_dispatch.py` closes that boundary by validating the existing `wwcx.cookie-monster.job.v1` envelope, resolving the dataset through a local runtime registry, and running the Alpha pipeline only against an explicitly enabled non-production read-only dataset.

## Runtime mapping

The mapping is deterministic and deliberately path-free:

```text
Big Bird job dataset=alpha-staging
        |
        v
/etc/wwcx-cookie-monster/datasets.json
  enabled=true
  non_production=true
  read_only=true
        |
        v
/srv/cookie-monster/datasets/alpha-staging   (read only source)
        |
        v
/var/lib/cookie-monster-alpha/generated/alpha-staging   (generated state)
```

Registry entries cannot supply a path. The dispatcher constructs `dataset_root / slug`, rejects symlink roots/components and verifies containment before ingestion. Unknown registry fields fail closed, so path, credential, URL or command-style additions cannot silently widen authority.

## Safe default registry

`config/cookie-monster/datasets.example.json` contains `alpha-staging` disabled by default. Enabling it is a runtime activation step and must happen only after the corresponding non-production directory has deliberately been created and reviewed.

## Job creation

Create a path-free Big Bird-style job envelope:

```bash
python3 server/cookie_monster_contract.py make \
  --dataset alpha-staging \
  --requested-by <actor> \
  > /tmp/cookie-monster-job.json
```

The job contains the dataset slug, pipeline stages and bounded resource budgets. It contains no source/output path, URL, command or secret.

## Dispatch

After a runtime registry and non-production dataset exist:

```bash
python3 server/cookie_monster_dispatch.py \
  --job /tmp/cookie-monster-job.json
```

Defaults:

```text
registry     /etc/wwcx-cookie-monster/datasets.json
dataset root /srv/cookie-monster/datasets
output root  /var/lib/cookie-monster-alpha/generated
```

The current Alpha dispatcher requires the complete ordered pipeline. Partial stage requests fail closed instead of pretending that stage-selective semantics are already supported.

`job-status.json` is written under the dataset-specific generated directory. On failure it records only the exception type, not exception text, to avoid leaking unexpected sensitive detail into operator state.

## Idempotency

Before ingestion, the dispatcher loads the dataset's existing `knowledge-records.jsonl`. Re-running the same deterministic Big Bird job against unchanged input therefore uses Cookie Monster's existing cross-run idempotency behavior rather than creating duplicate knowledge records.

## Cockpit publication

For this dataset, publish the generated cockpit state with the runtime publisher introduced by PR #518:

```bash
sudo python3 deploy/cookie_monster_runtime_publish.py \
  --generated-root /var/lib/cookie-monster-alpha/generated/alpha-staging \
  --apply
```

That remains a separate authenticated Edge1 runtime action. Source merge does not imply live publication.

## Validation

The dedicated regression suite covers:

- enabled + non-production + read-only registry requirements;
- deterministic containment and symlink rejection;
- source immutability during dispatch;
- generated job/status output;
- repeat-run knowledge-record reuse;
- rejection of partial pipeline requests;
- rejection of generated output beneath the dataset root;
- rejection of path/credential registry fields;
- sanitized failure state without exception text.

CI compiles the dispatcher with the Alpha/contract modules and runs `tests.test_cookie_monster_dispatch` before merge.

## Activation boundary

This package does not create `/srv/cookie-monster`, install runtime configuration, activate Fengus, publish the cockpit, change authentication, or expose a public service. The presently available Edge1 Operator connector is read-only, so live staging activation remains a separate authenticated deployment step.
