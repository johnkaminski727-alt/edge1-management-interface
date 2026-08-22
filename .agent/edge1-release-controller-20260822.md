# Edge1 Durable Release Controller — 2026-08-22

Status: repository implementation in review; live installation/promotion not yet claimed.

## Objective

Replace ambiguous in-place control-plane deployment with a durable source/runtime split and exact rollback.

## Implemented source direction

- dedicated source checkout: `/opt/edge1-management-source`
- immutable commit-pinned runtime releases: `/opt/edge1-runtime/releases/<sha>`
- atomic active pointer: `/opt/edge1-runtime/current`
- exact rollback pointer: `/opt/edge1-runtime/previous`
- fixed managed services: Edge1 Operations API + Edge1 Operator MCP only
- root-stability + mutations-disabled + loopback-listener postflight
- automatic pointer/drop-in/service rollback if target postflight fails
- persistent read-only five-minute status snapshot
- read-only Release Manager UI candidate
- exact-SHA attended `edge1_release` live-shell action
- automatic promotion deliberately disabled

## Authority boundaries

- no DNS/certificate/firewall/auth changes
- no arbitrary shell required
- no caller-provided path, branch, command, URL, service, or target SHA
- release target comes only from `EDGE1_RELEASE_TARGET_SHA` and must be an exact 40-character commit reachable from local `origin/main`
- Operations API mutations remain disabled
- Release Manager stays `staged_disabled` until live browser/runtime acceptance

## Live gate

Repository merge is not live deployment evidence. First live reconciliation must be attended through the authenticated write-capable sidecar, preserve rollback state, and prove both managed services, Operations API root stability, mutation denial, loopback listeners, persistent status, UI rendering and independent Edge1 state agreement before navigation promotion.

Tracking: issue #530.
