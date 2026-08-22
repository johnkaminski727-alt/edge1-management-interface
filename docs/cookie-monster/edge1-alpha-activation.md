# Cookie Monster Edge1 Alpha Activation

Status: source-ready bounded activation transaction; live execution requires an authenticated write-capable Edge1 path.

## Purpose

`deploy/cookie_monster_edge1_activate.py` is the final bounded transaction between the already-installed Cookie Monster foundation and a verified live Alpha staging run. It exists so an attended Edge1 operator does not need to improvise a sequence of root shell commands.

The transaction is deliberately narrow:

1. inspect the installed `alpha-staging` registry and filesystem state;
2. populate only the deterministic synthetic non-production dataset when the directory is empty;
3. keep the dataset filesystem read-only and flip only `alpha-staging.enabled` from false to true;
4. create the fixed path-free `wwcx.cookie-monster.job.v1` request;
5. dispatch the full Alpha pipeline into `/var/lib/cookie-monster-alpha/generated/alpha-staging`;
6. prove the source hashes did not change;
7. run one fixed `text.token-stats` Fengus work item through the hardened systemd worker;
8. verify provenance and acceptance criteria;
9. publish the minimized private Cookie Monster cockpit from the dataset-specific generated evidence root; and
10. retain a backup pointer for bounded rollback.

The transaction does **not** change DNS, certificates, firewall policy, Apache routing, authentication, canonical archive data, external accounts, Internet Archive, Zotero, Omeka, Paperless or ArchiveBox.

## Preconditions

The foundation installer must already have completed successfully:

```bash
sudo python3 deploy/cookie_monster_edge1_install.py --apply
```

That foundation must still provide:

- `/etc/wwcx-cookie-monster/datasets.json` with `alpha-staging` non-production, read-only and initially disabled;
- `/srv/cookie-monster/datasets/alpha-staging` as the dedicated staging source;
- `/var/lib/cookie-monster-alpha/generated` outside the staging source;
- the dedicated `cookie-monster-fengus` service identity and hardened worker unit; and
- the Fengus inbox/outbox directories.

The canonical Edge1 management repository must be clean and on the reviewed source revision before activation. Updating the ordinary repository workspace does not change the immutable production Edge1 Operator MCP runtime; those are separate deployment surfaces.

## Read-only preflight

Default invocation is non-mutating:

```bash
python3 deploy/cookie_monster_edge1_activate.py
```

Preflight fails closed when:

- the fixed Alpha source files are absent;
- the foundation registry is absent or contains unexpected authority-bearing fields;
- `alpha-staging` is not explicitly `non_production=true` and `read_only=true`;
- the staging path is missing, symlinked, writable, or contains anything other than the exact deterministic synthetic set;
- an enabled dataset is empty or otherwise unverified;
- generated state is a symlink/non-directory; or
- a required activation source is missing or symlinked.

Preflight does not populate the dataset, enable it, create a job, run Fengus or publish the cockpit.

## Apply

Live activation is root-only and restricted to the canonical Edge1 management repository:

```bash
sudo python3 deploy/cookie_monster_edge1_activate.py --apply
```

Before mutation the transaction creates:

```text
/var/backups/wwcx-cookie-monster-alpha-activation-<STAMP>-<PID>/
```

The backup records the prior dataset registry and job state. The runtime publisher creates its own independent backup before changing the private cockpit. The activation record retains that publisher backup so rollback can restore both control state and the operator view.

The synthetic source is four deterministic files including one exact duplicate. Files are written mode `0444`; the source directory remains non-writable. Re-running activation accepts the exact existing synthetic set and rejects any divergent content.

The generated job contains only the bounded dataset slug and resource budgets. It does not carry a source path, output path, URL, command or credential.

## Fengus proof

Activation selects a generated source asset ID and constructs one deterministic `wwcx.cookie-monster.fengus-work.v1` request with the fixed operation:

```text
text.token-stats
```

The request is delivered through the installed `cookie-monster-fengus-worker@.service` unit. The worker remains network-isolated and unable to see `/srv/cookie-monster`, the generated knowledge store or Edge1 Operations API credentials.

Successful completion updates the generated runtime status to record a verified bounded systemd worker and appends a sanitized activation audit event. No arbitrary command, path or archive authority is passed to Fengus.

## Live acceptance gate

Activation fails unless all of these are true:

- synthetic source hashes are unchanged across dispatch;
- at least one exact duplicate group is detected;
- `unauthorized_source_writes == 0`;
- every knowledge record resolves back to an expected staging file with the matching SHA-256; and
- the bounded Fengus systemd work item returns a verified result hash.

The resulting `acceptance.json` is written into the dataset-specific generated evidence directory. Only after that gate passes is the minimized private cockpit published with bounded staging detail.

## Rollback

Rollback restores control state and the previously published cockpit while preserving evidence:

```bash
sudo python3 deploy/cookie_monster_edge1_activate.py \
  --rollback /var/backups/wwcx-cookie-monster-alpha-activation-<STAMP>-<PID>
```

For the most recently successful activation:

```bash
sudo python3 deploy/cookie_monster_edge1_activate.py --rollback-last
```

Rollback restores the pre-activation registry and job file and invokes the runtime publisher's hash-verified rollback. It intentionally does **not** delete the synthetic source, generated knowledge/audit evidence, Fengus request/result evidence, service identity, or runtime directories.

## Operator transport

The canonical production `Edge1 Operator` app remains read-only and must not be widened merely for this rollout. The accepted escalation path is the separate attended Edge1 Live Shell sidecar or another authenticated write-capable Edge1 execution path.

When the sidecar is used, prefer a named fixed Cookie Monster activation action over generic `edge1_exec`. Raw shell should remain disabled by default. Before any live apply, verify host identity, principal, repository branch/cleanliness/current revision, foundation preflight, disk space, and current service/listener state.

## Current live gate

As of 2026-08-22, the published Edge1 Operator workspace still reports `mutations_enabled=false` and exposes only its reviewed read-only contract. The fresh host snapshot sees `/opt/edge1-management-interface` on `main`, while the long-running Operations API remains bound to an older resolved repository generation. Do not use that ambiguous Operations API process to mutate or repair the repository.

Source merge therefore does not constitute live activation. Live execution begins only after an authenticated write-capable operator path verifies the current host state.
