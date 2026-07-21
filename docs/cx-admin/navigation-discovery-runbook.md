# CX Admin Navigation Discovery Runbook

This runbook inventories the deployed CX Admin application before any menu or route change. It is intentionally read-only and must not be used to infer missing routes.

## Preconditions

- Use an authenticated shared-hosting shell with read access to the deployed CX Admin document root.
- Check out the repository branch or merged revision containing `tools/cx_admin/discover_navigation.py`.
- Do not copy environment files, credentials, database contents, customer records, runtime logs, or PHP source into evidence.

## Discover the actual admin root

Confirm the deployed directory from the hosting configuration or existing release procedure. Do not assume a path from memory. Set it only after verification:

```sh
ADMIN_ROOT=/verified/path/to/public_html/admin

test -d "$ADMIN_ROOT"
test -f "$ADMIN_ROOT/bigbird-operations-console.php"
```

The required known route is:

```text
/admin/bigbird-operations-console.php
```

## Run the read-only inventory

```sh
mkdir -p evidence/cx-admin-navigation

python3 tools/cx_admin/discover_navigation.py \
  "$ADMIN_ROOT" \
  --url-prefix /admin \
  --output evidence/cx-admin-navigation/routes.json
```

The JSON contains paths relative to the admin root, verified URL routes, extracted titles, authorization hints, outbound links, exclusion reasons, and source fingerprints. It does not contain full PHP source.

## Validate the inventory

```sh
python3 - <<'PY'
import json
from pathlib import Path

path = Path('evidence/cx-admin-navigation/routes.json')
data = json.loads(path.read_text(encoding='utf-8'))
required = '/admin/bigbird-operations-console.php'
routes = {page['route'] for page in data['pages']}
if required not in routes:
    raise SystemExit(f'missing required route: {required}')
print('pages:', data['page_count'])
print('navigable candidates:', data['navigable_candidate_count'])
print('required route: present')
PY
```

Review every candidate manually against its actual authorization and rendering behavior. A scanner result is evidence for review, not automatic permission to add a menu entry.

## Operations-centre comparison

Identify every candidate whose title, filename, links, or content describes an operations centre or operations console. For each one, record:

- verified route and title;
- authentication and authorization checks;
- monitored systems and data sources;
- available actions;
- cards, links, and workflows unique to that surface;
- overlap with `bigbird-operations-console.php`;
- owning deployment or subsystem.

Select and document one outcome: consolidate, parent-and-child, or retire-and-redirect. Never retain two ambiguous top-level entries called Operations Centre.

## Evidence handling

The sanitized route inventory may be attached to the implementation record after review. Do not commit absolute hosting paths if they disclose private account structure. Never commit copied application source, secrets, logs, sessions, database exports, or customer information.

## Required checks before menu deployment

- Unit tests for the discovery tool pass.
- All menu routes resolve to existing pages.
- All eligible pages are represented once.
- Desktop and mobile menus use the same registry.
- Permission metadata is present for every entry.
- Direct-route authorization remains enforced.
- The operations-centre consolidation decision is documented.
- A shared-hosting release and rollback procedure is prepared.
