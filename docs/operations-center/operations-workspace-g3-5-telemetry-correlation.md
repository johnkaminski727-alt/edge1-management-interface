# G3.5 — telemetry coverage, source correlation and drill-down

G3.5 improves the existing read-only Audit & ToolBox workspace without adding privileged reads, new services, shell execution or Apply.

## What changes

- **Telemetry coverage** summarizes the fixed, bounded source checks already returned by the authenticated G3 operations endpoint.
- Counts current supporting sources separately from stale, unavailable and unverified records.
- **Components with evidence gaps** identifies which existing security cards lack complete supporting evidence.
- **Shared-source correlations** highlights a degraded source that affects more than one component, helping distinguish one upstream telemetry problem from several independent component failures.
- Each flagged investigation card has a **Review Security evidence** control that navigates to the corresponding existing Security card. No new backend endpoint or raw source data is introduced.

## Safety model

All values are derived client-side from the already sanitized `/api/operations` response. Component names and source checks originate from server-side fixed whitelists. Dynamic values are inserted with `textContent`; no `innerHTML`, browser token persistence or command execution is added. A current source still does not prove packet enforcement, end-to-end reachability, collector correctness or policy intent.

## Deployment gate

G3.4 is installed and browser-accepted on Edge1. Keep G3.5 in draft until all existing repository, operator and G3 workflows are green. Install only from a pinned SHA after offline preflight, preserve the existing private G2 token/candidate database, restart only the manual SSH-tunneled G3 process, then browser-check telemetry coverage and drill-down behavior.
