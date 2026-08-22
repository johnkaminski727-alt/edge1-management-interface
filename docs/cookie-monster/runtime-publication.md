# Cookie Monster Runtime Publication

Status: source-ready, not yet activated on Edge1.

## Purpose

Cookie Monster runtime evidence must remain outside repository source, while the human-facing cockpit needs a stable private web location. `deploy/cookie_monster_runtime_publish.py` packages the static cockpit plus validated runtime snapshots into `/var/www/edge1-status/cookie-monster` without copying generated evidence into Git.

The publisher manages only:

- `index.html`
- `assets/mascot.webp`
- `status.json`
- `review-state.json`
- `job-status.json`
- `acceptance.json`
- `runtime-manifest.json`

`status.json` is required for an apply. Review, job and acceptance snapshots are optional; when an optional source is absent, a stale destination copy is removed after backup so the cockpit cannot present yesterday's state as current.

## Safety boundaries

The publisher fails closed when:

- repository source, generated evidence and runtime web roots overlap;
- the required Cookie Monster status file is absent;
- `status.json` does not use `wwcx.cookie-monster.alpha.v1`;
- any present runtime snapshot is not valid JSON;
- a runtime snapshot path is not a regular file.

Publication never modifies the staging source or generated evidence store. It does not change Apache, DNS, certificates, authentication, firewall rules or public routing.

## Preflight

The default command is read-only:

```bash
python3 deploy/cookie_monster_runtime_publish.py
```

Expected production paths:

```text
repo       /opt/edge1-management-interface
generated  /var/lib/cookie-monster-alpha/generated
web        /var/www/edge1-status/cookie-monster
backups    /var/backups
```

A successful preflight reports the current repository commit and which runtime snapshots are present.

## Apply

After an authenticated Edge1 operator has reviewed the current repository/runtime state and generated snapshot:

```bash
sudo python3 deploy/cookie_monster_runtime_publish.py --apply
```

Before mutation, every managed destination is backed up to a timestamped directory under `/var/backups`. The publisher then uses atomic replacement and writes `runtime-manifest.json` with SHA-256 hashes, byte counts, publication time and the source commit when available.

## Rollback

The apply output includes the exact backup directory. Roll back only with that retained path:

```bash
sudo python3 deploy/cookie_monster_runtime_publish.py \
  --rollback /var/backups/wwcx-cookie-monster-runtime-<STAMP>-<PID>
```

Rollback verifies the backup index and retained hashes, restores files that existed before publication, and removes only managed files that did not previously exist.

## Validation

Source validation for this package:

```bash
python3 -m py_compile deploy/cookie_monster_runtime_publish.py tests/test_cookie_monster_runtime_publish.py
python3 -m unittest -v tests.test_cookie_monster_runtime_publish
```

The tests cover read-only preflight, atomic publication, stale optional-state removal, malformed JSON rejection before mutation, exact managed-state rollback, source-tree separation and status-schema rejection.

## Activation boundary

This package closes the source-side runtime-publication gap only. Live Edge1 publication still requires an authenticated write-capable Edge1 execution path. The currently exposed Edge1 Operator connector is read-only, so source merge is not evidence of live deployment.
