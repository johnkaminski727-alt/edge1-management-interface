# G3.4: read-only contextual ToolBox (development preview)

This phase replaces the G3 Audit & ToolBox documentation placeholder with an operational investigation screen sourced **only** from the existing authenticated `/api/operations`, `/api/state`, and `/api/audit` routes.

## Capabilities

- Core and Network Defense observation cards, including independent freshness and age.
- Security investigation cards for components requiring review; status and known fixed-name monitoring-source status are shown independently. The full diagnostic evidence remains in Security.
- Saved-candidate pending-change count and the first 20 records from the existing bounded candidate audit endpoint.
- Manual refresh of the already authorized operations snapshot and candidate audit, plus links to operator guidance.

All inserted dynamic values use `textContent`, not `innerHTML`. The page neither persists private tokens to browser storage nor introduces shell commands, privileged reads, background listeners, Apply or firewall actions.

## Acceptance gate

G3.3 browser acceptance on Edge1 remains separate and pending until the user visually confirms the new Firewall aggregates, Fail2ban jail activity, and Evidence and next steps panels. G3.4 development must not automatically replace the installed G3.3 package before that acceptance. For G3.4, preflight from its pinned source revision with `deploy/candidate-workspace/install-g3.sh --check`, install only after deliberate operator approval and verify installed checksums. Restart the manually launched G3 server on the SSH-tunneled localhost port and test the ToolBox with fresh and stale sources.

No independent traffic-path verification, privileged RBAC, Apply, deployment or production security changes are provided by this release.
