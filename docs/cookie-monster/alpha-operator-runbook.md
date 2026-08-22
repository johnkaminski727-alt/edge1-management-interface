# Cookie Monster Alpha Operator Runbook

Status: operator procedure for a future non-production Edge1 activation. Source documentation only; this runbook is not evidence that Edge1 has been synchronized, installed, activated, or published.

## Purpose

This is the human-facing sequence for taking Cookie Monster Alpha from repository-ready source to one deliberately bounded non-production staging run without creating canonical archive authority.

The sequence is intentionally boring in the important places:

1. verify the exact source/runtime state;
2. establish the disabled foundation;
3. stage only non-production input;
4. explicitly enable one dataset slug;
5. dispatch through the bounded Big Bird-style contract;
6. prove source immutability and provenance;
7. publish only minimized operator views;
8. verify the cockpit as a human;
9. retain evidence and rollback points.

Do not skip from source merge directly to publication.

## Authority map

| Surface | Alpha authority |
| --- | --- |
| GitHub repository | Maintained source authority |
| Edge1 management checkout | Deployed source only after exact synchronization is verified |
| `/srv/cookie-monster/datasets/alpha-staging` | Deliberately non-production read-only staging input |
| `/var/lib/cookie-monster-alpha/generated/alpha-staging` | Generated runtime/evidence state |
| `/var/www/edge1-status/cookie-monster` | Derived operator/browser view only; never evidence authority |
| Big Bird job envelope | Bounded orchestration request by dataset slug; no paths/URLs/commands/credentials |
| Fengus | Bounded data-only worker; no archive credentials or direct archive authority |
| Canonical archive / WW.CX Digital Archive | Outside Alpha staging authority; no implicit read/write grant |
| Human review | Admin/operator-owned; web approve/reject transport remains disabled until separately authenticated and assigned |

Paperless-ngx, ArchiveBox, Omeka S and other WW.CX Digital Archive components remain processing/catalog/publication layers around a separately governed evidence authority. Their existence does not turn a Cookie Monster staging run into canonical-archive access.

## Hard stops

Stop rather than improvise if any of these are true:

- the Edge1 checkout is not the explicitly intended GitHub commit or documented descendant;
- the management checkout has local modifications that have not been reconciled;
- the dataset is canonical, production, customer-authoritative, or otherwise not clearly disposable/non-production staging;
- the staging directory contains symlinks or path escapes;
- the runtime registry contains filesystem paths, URLs, commands, credential fields or unknown authority-bearing fields;
- `alpha-staging` is already enabled before its contents and ownership have been reviewed;
- a step would require credentials to be placed in Git, a job envelope, chat, or a browser-visible snapshot;
- an action would start Fengus, enable web mutations, change Apache/DNS/certificates/firewall/authentication, or expose a new listener without its own reviewed deployment authority;
- generated evidence reports any unauthorized source write or provenance gap;
- the browser route/access boundary is not understood well enough to decide what detail may be published.

## Phase 0 — repository and live-state gate

The repository merge state and Edge1 runtime state are separate facts.

Before touching Cookie Monster runtime state, record:

```bash
cd /opt/edge1-management-interface
git status --short --branch
git rev-parse HEAD
git rev-parse origin/main
```

Also verify the bounded operator/Operations API remains healthy and mutation policy has not changed unexpectedly.

Acceptance for this phase:

- intended commit is known;
- checkout is clean or any differences are explicitly reconciled;
- no source synchronization is inferred from GitHub alone;
- Operations API mutation state is understood before deployment work begins.

If synchronization is needed, use the existing authenticated repository/deployment workflow. Do not invent a second checkout or copy individual files by hand merely to make the hashes line up.

## Phase 1 — foundation preflight

Run the foundation installer without `--apply`:

```bash
cd /opt/edge1-management-interface
python3 deploy/cookie_monster_edge1_install.py
```

Confirm the preflight reports a disabled, non-production, read-only example registry and the expected hardened Fengus unit.

Expected invariant after preflight: **nothing has changed**.

## Phase 2 — install the disabled foundation

Only through an authenticated write-capable Edge1 path and after reviewing the preflight:

```bash
sudo python3 deploy/cookie_monster_edge1_install.py --apply
```

Record the exact backup directory reported by the installer.

Expected foundation:

```text
/etc/wwcx-cookie-monster/datasets.json
/etc/systemd/system/cookie-monster-fengus-worker@.service
/srv/cookie-monster/datasets/alpha-staging
/var/lib/cookie-monster-alpha/generated
/var/lib/cookie-monster-alpha/fengus/inbox
/var/lib/cookie-monster-alpha/fengus/outbox
```

Required postconditions:

- registry entry remains `enabled: false`;
- `alpha-staging` is non-production and read-only by policy;
- the staging directory exists but no canonical source has been mounted or copied into it;
- no Fengus template instance is running;
- no new network listener exists;
- the backup path is retained.

Foundation rollback, if required, uses the exact path returned by apply:

```bash
sudo python3 deploy/cookie_monster_edge1_install.py \
  --rollback /var/backups/wwcx-cookie-monster-alpha-foundation-<STAMP>-<PID>
```

Do not guess the timestamp. Rollback intentionally preserves runtime directories and service-account identity rather than destructively deleting evidence or invalidating ownership.

## Phase 3 — populate one non-production staging dataset

The operator selects input here. Alpha does not discover its own authority.

Populate only:

```text
/srv/cookie-monster/datasets/alpha-staging
```

Before enabling the registry entry, capture a source inventory suitable for later immutability comparison. At minimum record relative paths, sizes, mtimes and SHA-256 hashes.

Rules:

- originals remain untouched;
- no symlinks;
- no mount or bind that silently exposes a canonical archive;
- no credentials, secrets, private keys or token stores;
- no generated-output directory inside the staging tree;
- do not rename, normalize, transcode, deduplicate or "clean up" originals as part of staging ingestion.

If the staging dataset cannot be clearly distinguished from canonical evidence, stop here.

## Phase 4 — deliberately enable only `alpha-staging`

Review `/etc/wwcx-cookie-monster/datasets.json` immediately before the change.

The only activation shape accepted for the staged dataset is conceptually:

```json
{
  "enabled": true,
  "non_production": true,
  "read_only": true
}
```

The registry must remain path-free. Dataset location is deterministic from the slug:

```text
alpha-staging
  -> /srv/cookie-monster/datasets/alpha-staging
```

Do not add a source path, archive path, URL, command, credential or secret to the registry to solve an operational inconvenience.

After enabling, re-read the registry and verify that no other dataset was activated.

## Phase 5 — create the bounded Big Bird-style job

Generate the contract rather than hand-authoring an authority-bearing payload:

```bash
cd /opt/edge1-management-interface
python3 server/cookie_monster_contract.py make \
  --dataset alpha-staging \
  --requested-by <authenticated-operator> \
  > /tmp/cookie-monster-job.json
```

Inspect the job before dispatch. It may carry the dataset slug, ordered pipeline stages, actor and resource budgets. It must not carry filesystem paths, URLs, commands, credentials or secrets.

## Phase 6 — bounded dispatch

Run:

```bash
python3 server/cookie_monster_dispatch.py \
  --job /tmp/cookie-monster-job.json
```

Default runtime mapping:

```text
registry     /etc/wwcx-cookie-monster/datasets.json
dataset      /srv/cookie-monster/datasets/alpha-staging
generated    /var/lib/cookie-monster-alpha/generated/alpha-staging
```

The current Alpha dispatcher requires the complete ordered pipeline. A partial-stage request should fail closed.

Do not turn a dispatcher rejection into an excuse to pass an arbitrary source path directly to another script.

## Phase 7 — acceptance and evidence review

After dispatch, compare the staging source against the Phase 3 inventory.

Required evidence:

- source byte hashes unchanged;
- source mtimes unchanged unless a separately understood filesystem behavior explains otherwise;
- `unauthorized_source_writes == 0`;
- no provenance gaps;
- duplicate detection does not alter originals;
- generated state is outside the source tree;
- a repeat run against unchanged input reuses knowledge records rather than duplicating them;
- audit history remains append-only;
- job failure state, if any, does not disclose exception text or secret material.

The deterministic synthetic M6 harness remains a useful regression gate:

```bash
python3 server/cookie_monster_acceptance.py
```

For live-staging acceptance, do **not** substitute the synthetic harness result for inspection of the actual staged dataset evidence. The synthetic PASS proves the mechanism; the staged run proves this activation.

If any provenance gap or source write is observed, do not publish the cockpit as healthy. Disable the dataset entry and preserve the evidence for review.

## Phase 8 — build/publish the minimized cockpit view

Preflight the runtime publisher against the dataset-specific generated root:

```bash
sudo python3 deploy/cookie_monster_runtime_publish.py \
  --generated-root /var/lib/cookie-monster-alpha/generated/alpha-staging
```

Default publication is summary-only. Raw generated metadata is not a browser contract.

If and only if the route/access boundary has been reviewed and file-level staging detail is appropriate, the operator may deliberately request bounded filename/location detail:

```bash
sudo python3 deploy/cookie_monster_runtime_publish.py \
  --generated-root /var/lib/cookie-monster-alpha/generated/alpha-staging \
  --publish-detail
```

`--publish-detail` still excludes raw ffprobe/MediaInfo/EXIF payloads, metadata-tool paths and unallowlisted knowledge facts. It should fail unless the source is explicitly Alpha read-only non-production staging with zero unauthorized source writes.

After reviewing the preflight, publication is the separate mutation:

```bash
sudo python3 deploy/cookie_monster_runtime_publish.py \
  --generated-root /var/lib/cookie-monster-alpha/generated/alpha-staging \
  --apply
```

Or, when bounded detail was explicitly approved:

```bash
sudo python3 deploy/cookie_monster_runtime_publish.py \
  --generated-root /var/lib/cookie-monster-alpha/generated/alpha-staging \
  --publish-detail \
  --apply
```

Retain the exact backup path printed by the publisher.

## Phase 9 — human cockpit acceptance

This phase is not optional. A successful backend run is not the same thing as a usable system.

Open the real Cookie Monster browser route through its intended operator access path and verify at least:

- mascot and page load correctly;
- Dashboard shows the current run, not demo/stale data;
- "What it ate" behaves correctly for summary-only versus explicit detail mode;
- duplicate counts agree with generated evidence;
- "What it learned" does not expose raw hidden metadata by accident;
- "Needs human eyes" shows review state without performing an unauthenticated mutation;
- Big Bird job state matches the dispatched job;
- M6/acceptance view distinguishes synthetic evidence from live staging evidence;
- Provenance state is understandable to a human operator;
- Fengus clearly shows bounded/not-activated state unless a separate later deployment says otherwise;
- browser refresh does not regress to stale snapshots;
- unknown/missing data is displayed as unknown/not run, never silently healthy.

Do not promote Cookie Monster into shared operator navigation until the actual route and owning access-control boundary have been verified live.

## Phase 10 — review actions remain human-gated

The Alpha UI may generate bounded review CLI commands. It does not gain mutation authority from being visible in a browser.

Until a separately reviewed authenticated mutation transport exists:

- no web approve/reject endpoint;
- no inference that navigation grants authorization;
- no auto-approval by Big Bird, Cookie Monster or Fengus;
- no knowledge-record rewrite to encode the decision.

Review decisions remain append-only events under the bounded review state machine.

## Phase 11 — Fengus remains a separate activation

Foundation installation may create the dedicated nologin service identity and install the hardened unit template. That does not authorize starting a worker instance.

Before any later Fengus activation, independently verify:

- operation allowlist remains data-only;
- worker payload contains no path/URL/command/credential/secret fields;
- `PrivateNetwork=yes` and strict filesystem controls remain present;
- canonical archive and sensitive operation paths remain inaccessible;
- resource/time limits are bounded;
- the work item is generated/derived data, not direct archive authority.

Credentials are not a workaround for missing architecture. If a future worker truly requires a secret, that is a separate design and deployment decision.

## Rollback / safe stop matrix

| Problem | Safe response |
| --- | --- |
| Checkout mismatch | Stop; reconcile source through the normal authenticated repo workflow |
| Foundation preflight mismatch | Do not apply |
| Existing registry differs | Preserve it; investigate rather than overwrite |
| Staging source uncertain/canonical | Do not enable dataset |
| Dispatcher boundary rejection | Fix the bounded contract/config; do not pass raw paths around it |
| Source hash/mtime change | Disable dataset, preserve generated/audit evidence, investigate |
| Provenance gap | Treat run as failed; do not publish healthy state |
| Browser reveals excessive detail | Roll back publication and keep summary-only mode |
| Stale optional browser state | Re-run publisher; stale optional files should be removed atomically |
| Publication problem | Use exact runtime-publication backup path for rollback |
| Fengus isolation doubt | Do not start worker |

Runtime publication rollback:

```bash
sudo python3 deploy/cookie_monster_runtime_publish.py \
  --rollback /var/backups/wwcx-cookie-monster-runtime-<STAMP>-<PID>
```

## Completion record

An Alpha activation is complete only when the retained evidence can answer all of these without hand-waving:

- Which exact repository commit was deployed?
- Which exact non-production dataset slug was enabled?
- What source inventory/hash baseline was captured before ingestion?
- Were source bytes and mtimes unchanged afterward?
- What job ID/idempotency key ran?
- What knowledge records were created versus reused?
- Were there any provenance gaps?
- Were there any unauthorized source writes?
- What review decisions occurred, by whom, and in what append-only chain?
- What operator-view detail level was published?
- What exact runtime publication backup can restore the previous cockpit?
- Did a human verify the real UI and access boundary?
- Was Fengus left inactive unless separately authorized?
- Did any action touch canonical archive authority, DNS, certificates, firewall, authentication or public routing? The Alpha answer should be **no**.

If those questions cannot be answered from evidence, the activation is not complete.
