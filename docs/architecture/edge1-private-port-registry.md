# Edge1 private listener registry

This register documents the intended ownership of selected private
Edge1 listener ports. It is an architecture constraint, not evidence
that a service is currently healthy.

| Port | Owner | Purpose | Exposure |
| --- | --- | --- | --- |
| 8097 | Edge1 Operations API | Authenticated internal operations API | Loopback only |
| 8098 | Edge1 Private Web Gateway | Private web applications and allowlisted gateway routes | Loopback only |
| 8102 | Edge1 MCP transport | Private MCP transport | Loopback only |
| 18098 | Historical WW.CX Portal API Bridge | Dormant reservation; retained carrier/portal bridge only when explicitly run | Loopback only; no standing listener |

## Access model

The architecture keeps three concerns separate:

1. private network reachability;
2. human authentication;
3. application authorization.

Ports 8097 and 8098 must not be made public merely to simplify browser
access.

SSH forwarding to 8098 is an administrative/development fallback.
It is not the intended permanent user experience.

The Edge1 Private Access Gateway workstream is responsible for providing
stable private browser addresses and mobile-friendly human
authentication while preserving the loopback-only application boundary.

The browser must not require Operations API HMAC secrets or equivalent
service credentials.

## Shared interface rule

Participating Edge1 Intelligence pages use the canonical navigation
manifest at:

`src/web/shared/intelligence-nav.json`

Navigation is generated with:

`tools/web/generate_intelligence_nav.py`

Pages declare only their active module. Generated navigation must pass
the `--check` validation before deployment.
