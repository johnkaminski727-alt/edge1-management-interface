# Cookie Monster Alpha Runtime Packaging

Status: source-ready, runtime disabled by default.

This package closes the gap between the merged Cookie Monster source and a future Edge1 non-production staging run without silently activating a canonical archive or privileged web mutation.

## Dataset registry

`config/cookie_monster/datasets.json` maps bounded dataset names to staging-only source roots. The initial `synthetic-media-v1` entry is deliberately `enabled: false`, `canonical_archive: false`, and `read_only_required: true`.

`server/cookie_monster_runtime.py` accepts a validated `wwcx.cookie-monster.job.v1` request, resolves only a registered enabled dataset, refuses canonical datasets, and refuses source roots outside `/srv/cookie-monster/staging/`.

Callers therefore select **what approved dataset** to process rather than supplying an arbitrary filesystem path.

## Browser/operator evidence minimization

Raw ingestion state is not copied directly to the browser tree. `server/cookie_monster_operator_view.py` creates a separate bounded operator-view directory.

- external metadata payloads such as raw EXIF/MediaInfo/ffprobe structures are never projected;
- executable/tool filesystem paths are removed;
- source filenames/relative locations and record facts are omitted unless that dataset explicitly sets `operator_detail_publish: true`;
- unknown or future datasets therefore fail closed to summary-only display;
- the initial synthetic dataset opts into detail because its contents are deterministic non-production fixtures.

The raw append-only `knowledge-records.jsonl`, `audit.jsonl`, and `review-decisions.jsonl` remain outside the web root.

## Operator UI publisher

`deploy/cookie-monster/publish.sh` is dry-run by default and consumes `/var/lib/cookie-monster-alpha/operator-view`, not the raw generated evidence directory.

Preflight:

```bash
cd /opt/edge1-management-interface
./deploy/cookie-monster/publish.sh
```

Future apply, only after the intended checkout and staging evidence are verified:

```bash
sudo ./deploy/cookie-monster/publish.sh --apply
```

The publisher copies only:

- the Cookie Monster HTML cockpit;
- the mascot WebP;
- bounded derived views: `status.json`, `review-state.json`, `job-status.json`, and `acceptance.json` when present.

Apply creates a timestamped `/var/backups/wwcx-cookie-monster-<UTC>/` backup and exact rollback script before changing the web destination. Missing derived runtime views are removed from the web destination so stale evidence is not presented as current evidence.

## Authority boundary

This source package does not:

- enable the staging dataset;
- create `/srv/cookie-monster/staging/...`;
- create a service account;
- activate the Fengus worker;
- publish to Edge1;
- add an authenticated approval mutation endpoint;
- grant access to a canonical archive.

Those remain explicit runtime/deployment acceptance steps.
