# Edge1 Security-Boundary Live Inventory Validation

Date: 2026-07-30  
Branch: `ops/edge1-security-boundary-live-inventory-20260730`

## Required repository checks

- Python compilation and unit tests pass.
- Shell syntax validation passes.
- JSON documents parse.
- Authorization contract records all four programs and immutable guardrails.
- Inventory writes only beneath the protected evidence directory.
- No service control, Apache mutation, route mutation, DNS, firewall, routing, IDS, reputation, certificate, listener, or traffic command exists.
- No Git remote URL, environment dump, SSH material, private key, shadow data, password-file content, token, cookie value, or client secret is collected.
- Unit and HTTP evidence is redacted.
- Apache directive values are not recorded.
- Exact filesystem inventory contains only path, SHA-256, mode, and bytes.
- Unknown artifacts remain `preserve_review`.
- Missing exact artifacts are reported.
- Duplicate source or target mappings fail closed.
- Staging and cutover remain false under committed policies.
- Changed-file scope, zero-behind state, mergeability, and review threads are verified at exact head.

## Execution authority

GitHub Actions is the authoritative repository validation path because the authoring runtime cannot resolve `github.com` for a local clone and has no authenticated Edge1 shell.

## Live acceptance remains separate

Repository success does not establish a live inventory. A live claim requires protected evidence from an authenticated Edge1 execution of the merged script.
