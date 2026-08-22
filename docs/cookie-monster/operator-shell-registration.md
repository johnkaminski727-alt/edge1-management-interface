# Cookie Monster Operator-Shell Registration

Status: repository-staged only. This document does not establish a live browser route, authentication policy, deployment state, or runtime health claim.

## Purpose

Cookie Monster Alpha has a human-facing cockpit in `src/web/cookie-monster/`. The canonical Edge1 Operator registry now records that cockpit as a staged module so its intended operator location is explicit before live activation.

Candidate route:

```text
/edge1-status/cookie-monster/
```

Registry state:

```text
id                    cookie-monster
browser_route         null
candidate_route       /edge1-status/cookie-monster/
runtime_route         /edge1-status/cookie-monster/
availability          staged_disabled
authorization         unverified_route_policy
palette               false
toolbox               false
evidence_status       verified_repository_unaccepted_browser
```

## Why `browser_route` is null

The Edge1 Operator shell renders navigation only for modules whose registry state is `accepted_live` and whose `browser_route` is a rooted browser path. Cookie Monster has source-level runtime publication machinery and a defined candidate location, but the live Edge1 checkout, runtime publication, route exposure, and owning access-control boundary have not yet been accepted together.

Leaving `browser_route` null prevents the navigation registry from becoming an accidental authorization or deployment claim.

## Promotion gate

Cookie Monster may move from staged evidence to live navigation only after all of the following are independently verified on Edge1:

1. the live management checkout is the intended merged commit or a documented descendant;
2. the Cookie Monster foundation is installed with the staging dataset still disabled by default;
3. one deliberately non-production staging dataset is activated and processed with zero unauthorized source writes and zero provenance gaps;
4. minimized operator-view JSON is published through the backup-first runtime publisher;
5. the real browser route loads the current cockpit and not stale/demo state;
6. the route's authentication/authorization owner is known and direct requests are protected by that owning boundary;
7. review approve/reject remains non-mutating in the browser unless a separately reviewed authenticated mutation transport exists;
8. Fengus is not implicitly activated by navigation publication;
9. listener/public-exposure state has not expanded unexpectedly;
10. rollback artifacts are retained.

Only after that evidence exists should the registry be changed to an accepted live browser route and palette/ToolBox visibility be reconsidered.

## Safety invariant

Navigation visibility does not grant authority. A staged module must not be promoted merely because its static files exist or a publisher can copy them into a web root.
