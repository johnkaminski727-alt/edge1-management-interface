# Cookie Monster Edge1 live acceptance — 2026-10-07

Cookie Monster remains a subsystem separate from the Edge1 Doom Cookie defensive authentication control. No Doom Cookie code, evidence store, signing key, policy or service ownership is part of Cookie Monster.

## Commissioned state

- Foundation installed with the dedicated `cookie-monster-fengus` nologin identity.
- `alpha-staging` is registered as non-production and read-only.
- Synthetic bounded staging activation completed successfully.
- Live acceptance result: PASS.
- Four staging files produced three unique assets and one duplicate group.
- Unauthorized source writes: 0.
- Provenance gaps: 0.
- Fengus jobs outside the allowlist: 0.
- The bounded Fengus one-shot worker completed successfully and is not a continuously running service.
- The minimized cockpit is published under `/var/www/edge1-status/cookie-monster`.
- Browser route: `/edge1-ops/status/cookie-monster/` through the existing authenticated Edge1 session boundary.
- An unauthenticated HTTPS request to the browser route redirects to the existing Edge1 login handoff.
- The legacy candidate path `/edge1-status/cookie-monster/` remains unavailable (404), avoiding an unprotected alternate route.

## Installer correction found during commissioning

The original foundation installer created `/var/lib/cookie-monster-alpha` as `root:root 0750`, which prevented the dedicated Fengus account from traversing to its own private working directory. Activation failed closed at the systemd `CHDIR` step. The installer now assigns the runtime parent to `root:cookie-monster-fengus 0750` while preserving the generated evidence directory as `root:root 0750`. Managed directory metadata is re-applied on subsequent installer runs so an interrupted or older installation can be repaired deterministically.

## Separation from Doom Cookie

Doom Cookie remains owned by `edge1-security-auth.service` and `/var/lib/wwcx-edge1-ops/doom-cookie`. Cookie Monster uses `/srv/cookie-monster`, `/var/lib/cookie-monster-alpha`, and the static authenticated cockpit publication tree. The commissioning process did not modify Doom Cookie state or its service drop-in; its evidence-chain verification remained passing during the Cookie Monster foundation installation.
