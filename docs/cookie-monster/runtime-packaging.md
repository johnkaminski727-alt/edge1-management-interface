# Cookie Monster Alpha Runtime Packaging

Status: source-ready, runtime disabled by default.

This package closes the gap between the merged Cookie Monster source and a future Edge1 non-production staging run without silently activating a canonical archive or privileged web mutation.

## Dataset registry

`config/cookie_monster/datasets.json` maps bounded dataset names to staging-only source roots. The initial `synthetic-media-v1` entry is deliberately `enabled: false`, `canonical_archive: false`, and `read_only_required: true`.

`server/cookie_monster_runtime.py` accepts a validated `wwcx.cookie-monster.job.v1` request, resolves only a registered enabled dataset, refuses canonical datasets, and refuses source roots outside `/srv/cookie-monster/staging/`.

Callers therefore select **what approved dataset** to process rather than supplying an arbitrary filesystem path.

## Operator UI publisher

`deploy/cookie-monster/publish.sh` is dry-run by default.

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
- bounded derived JSON views: `status.json`, `review-state.json`, `job-status.json`, and `acceptance.json` when present.

It intentionally does **not** publish raw `knowledge-records.jsonl`, `audit.jsonl`, or `review-decisions.jsonl`.

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
