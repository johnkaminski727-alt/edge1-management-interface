# Cookie Monster Runtime Publication

Status: source-ready, not yet activated on Edge1.

## Purpose

Cookie Monster runtime evidence must remain outside repository source, while the human-facing cockpit needs a stable operator web location. `deploy/cookie_monster_runtime_publish.py` packages the static cockpit plus a **minimized browser view** of validated runtime snapshots into `/var/www/edge1-status/cookie-monster` without copying generated evidence into Git.

The publisher manages only:

- `index.html`
- `assets/mascot.webp`
- `status.json`
- `review-state.json`
- `job-status.json`
- `acceptance.json`
- `runtime-manifest.json`

`status.json` is required for an apply. Review, job and acceptance snapshots are optional; when an optional source is absent, a stale destination copy is removed after backup so the cockpit cannot present yesterday's state as current.

The generated evidence store remains authoritative for full internal runtime evidence. The web-root JSON files are derived operator views, not archive records and not a second evidence authority.

## Browser minimization boundary

Raw runtime JSON is **never copied directly** to the web root.

Default publication is summary-only. It exposes the counts/state needed by the cockpit while withholding:

- raw ffprobe, MediaInfo or EXIF payloads;
- metadata-tool filesystem paths;
- asset filenames and relative source locations;
- raw knowledge-record facts;
- internal Fengus paths;
- arbitrary acceptance detail strings;
- the generated-evidence filesystem path.

The web `status.json` uses `wwcx.cookie-monster.operator-view.v1` and records the originating status schema separately as `source_schema`.

A deliberately reviewed Alpha staging run may opt into bounded file-level detail with:

```bash
--publish-detail
```

That option still does not publish raw metadata or tool paths. It fails closed unless all of these are true:

- `mode == alpha-read-only`;
- `source_kind` is `staging` or `non-production-staging`;
- `unauthorized_source_writes == 0`.

This flag is not archive-read authority and does not relax the source read-only boundary.

## Safety boundaries

The publisher fails closed when:

- repository source, generated evidence and runtime web roots overlap;
- the required Cookie Monster status file is absent;
- `status.json` does not use `wwcx.cookie-monster.alpha.v1`;
- any present runtime snapshot is not valid JSON;
- a runtime or static publication source is a symlink;
- a runtime snapshot path is not a regular file;
- detail publication is requested for evidence outside the bounded Alpha staging state.

Publication never modifies the staging source or generated evidence store. It does not change Apache, DNS, certificates, authentication, firewall rules or public routing.

## Preflight

The default command is read-only:

```bash
python3 deploy/cookie_monster_runtime_publish.py
```

Expected runtime paths:

```text
repo       /opt/edge1-management-interface
generated  /var/lib/cookie-monster-alpha/generated
web        /var/www/edge1-status/cookie-monster
backups    /var/backups
```

A successful preflight reports the current repository commit, which runtime snapshots are present, and whether file-level detail would be published. Preflight also builds and validates the minimized views in memory before any destination mutation occurs.

## Apply

After an authenticated Edge1 operator has reviewed the current repository/runtime state and generated snapshot:

```bash
sudo python3 deploy/cookie_monster_runtime_publish.py --apply
```

For an explicitly reviewed non-production Alpha dataset where bounded filename/location visibility is appropriate:

```bash
sudo python3 deploy/cookie_monster_runtime_publish.py --publish-detail --apply
```

Before mutation, every managed destination is backed up to a timestamped directory under `/var/backups`. The publisher then uses atomic replacement and writes `runtime-manifest.json` with SHA-256 hashes and byte counts of the **published operator-view files**, publication time, source commit, and the `detail_published` state.

The manifest records a logical evidence origin instead of exposing the generated evidence filesystem path.

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

The tests cover read-only preflight, minimized browser output, explicit bounded detail publication, raw metadata/path exclusion, symlink rejection, atomic publication, stale optional-state removal, malformed JSON rejection before mutation, exact managed-state rollback, source-tree separation and status-schema rejection.

## Activation boundary

This package closes the source-side runtime-publication and browser-minimization gap only. Live Edge1 publication still requires an authenticated write-capable Edge1 execution path. The currently exposed Edge1 Operator connector is read-only, so source merge is not evidence of live deployment.

The Cookie Monster browser route must not be promoted in shared operator navigation until its real access-control boundary and live browser acceptance are verified.
