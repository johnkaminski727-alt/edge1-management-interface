# CX Admin navigation registry readiness

## Current state

The production shared-hosting inventory completed on 2026-07-21 and verified 13 directly navigable PHP routes from 42 scanned files. The hardened scanner excluded bootstrap files, private source trees, renderers, API and action handlers, and deployment payloads.

The repository discovery registry is intentionally disabled and marked `discovery_only`. It records verified routes without inventing labels, sections, ordering, or authorization metadata.

## Verified routes

- `/admin/bigbird-ai-chat.php`
- `/admin/bigbird-automation.php`
- `/admin/bigbird-changes-audit.php`
- `/admin/bigbird-dns-cache.php`
- `/admin/bigbird-dns-queries.php`
- `/admin/bigbird-firewall.php`
- `/admin/bigbird-logs.php`
- `/admin/bigbird-operations-console.php`
- `/admin/bigbird-overview.php`
- `/admin/bigbird-security.php`
- `/admin/bigbird-settings.php`
- `/admin/bigbird-vpn-devices.php`
- `/admin/print-production.php`

## Production evidence

- Inventory schema: 2
- PHP files scanned: 42
- Navigable candidates: 13
- Sanitized inventory SHA-256: `b975469d3a4b0a69c37d86e32c711d28d42162de1b315a8abab81c7675b32cd0`
- Hardened scanner SHA-256: `a374ecb37958ddf1ce47330cfa1f1717d11ba758a1dbae76abd4454108f56801`
- Required Operations Console route: present
- Shared-hosting Python runtime: 3.6.8

The unsanitized inventory, source code, credentials, runtime data, and private absolute paths must not be committed.

## Remaining menu-readiness work

Before generating or deploying the live menu, inspect each verified page and the common admin renderer to establish:

1. authoritative display label;
2. menu section and sort order;
3. required role or permission;
4. feature or availability predicate;
5. whether the page belongs in desktop navigation, mobile navigation, or both;
6. the canonical relationship between Overview and Operations Console surfaces.

Do not derive authorization from filenames or assume every page has the same access policy.

## Validation

Run:

```sh
python3 tools/cx_admin/validate_navigation_registry.py
python3 -m unittest tests/test_cx_admin_navigation_registry.py
```

The discovery registry should pass structural validation but deliberately fail:

```sh
python3 tools/cx_admin/validate_navigation_registry.py --require-menu-ready
```

That failure is the deployment gate until every route has verified label, section, ordering, and authorization metadata.

## Deployment boundary

No live shared-hosting menu change is included in this phase. After the registry becomes menu-ready, prepare a separate reviewed patch, run PHP syntax and navigation-integrity checks, capture a timestamped backup, and deploy through the shared-hosting release and rollback procedure.
