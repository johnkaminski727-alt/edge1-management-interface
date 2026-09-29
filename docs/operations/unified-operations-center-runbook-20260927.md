# Edge1 Unified Operations Center — deployment and operations runbook
**Release:** 2026-09-27 · **Merge:** PR #592, squash commit `9109606740f5e225ebba6301158ddc7658be391e`  
**Scope:** localhost-only, read-only Operations Center frontend and its four observation collectors.

## Accepted state and boundaries
The operator confirmed all six browser acceptance checks. A subsequent read-only parity audit found **10/10 frontend assets identical** between the synchronized local `main` and `/var/www/edge1-status`, four of four live routes returning HTTP 200, and the private web service and four collector timers active. These are acceptance observations from 2026-09-27, **not a promise of current health**. The core collector reported 11/11 monitored services active and a 34-second-old snapshot during its earlier acceptance.

Only four routes are accepted live:
| Module | Private route |
| --- | --- |
| Operations Center | `/edge1-status/` |
| Security Operations | `/edge1-status/security/` |
| Security Correlation | `/edge1-status/security/correlation.html` |
| Network & DNS Defense | `/edge1-status/network-defense/` |

All pages use `src/web/operator-shell/shell.{css,js}` and `config/edge1_operator/navigation_registry.json`. Bitcoin/Mining remain `staged_disabled`; other modules retain their own unaccepted or separate-runtime classifications. The sidebar, ToolBox and search do not confer permissions. Historical telemetry appears inside the expandable **Legacy & Unconnected Telemetry** section; unavailable data is not healthy.

**Security Operations:** live CrowdSec cards coexist with legacy Suricata sections; Suricata data has not been accepted as a working collector on this installation. **Security Correlation:** the sanitized CrowdSec feed was observed with one genuine SSH event and zero independently verified cross-source correlations; filtering excludes known test alerts and source IP addresses. **Network Defense:** the observed-core/CrowdSec integration was limited (five of eleven components observed at acceptance). No IDS, independent DNS filtering-policy verification, IPv6 VPN forwarding or unavailable historical source should be represented as operational.

## Source, runtime and private access
Repository: `/opt/edge1-management-interface` on Edge1; canonical source is synchronized `main`. Frontend destination: `/var/www/edge1-status`. The Edge1 private web gateway listens only at `127.0.0.1:8098`, serves approved static content from `/var/www`, and proxies only explicitly allowlisted API routes to the authenticated Operations API on `127.0.0.1:8097`. It is not a public listener.

Until the Edge1 Private Access Gateway is enrolled, an authorized Windows operator may use the approved SSH-forwarding route to reach `127.0.0.1:8098`. This is an administrative/development fallback, not the intended permanent user experience. Normal access should ultimately use a stable private Edge1 address with mobile-friendly human authentication and application authorization, without manual SSH port forwarding or browser-held API/HMAC secrets. Do not expose 8098 publicly. Check mobile navigation and the four route destinations after any change.

## Preflight, publish and rollback
**Run on Edge1.** Publishing is a deliberate operator action, **not part of normal monitoring**.

```bash
cd /opt/edge1-management-interface
git status --short
git rev-parse --short HEAD
bash deploy/operations-center/publish.sh
```

Preflight checks that the ten frontend and shared-navigation source assets exist. Compare the intended Git revision, source diff and current runtime before deploying. If a new release is authorized and its source is reviewed, publish:

```bash
sudo bash /opt/edge1-management-interface/deploy/operations-center/publish.sh --apply
```

The publisher first backs up each of the ten previous frontend assets to `/var/backups/edge1-unified-publish-<UTC stamp>/previous/` and writes a manifest and `rollback.sh`. It then installs the assets. The publisher is **not transactional**: interruption during installation can leave a partial frontend update. Preserve the printed backup path and run route/asset/browser checks immediately after publishing. It neither installs collector executables/systemd units nor changes runtime JSON snapshots or traffic controls. Changes to collector deployment need a separately reviewed, backed-up installation procedure.

If a published frontend fails acceptance, inspect the saved manifest and execute the rollback script from the specific deployment, as root:

```bash
sudo bash /var/backups/edge1-unified-publish-<UTC stamp>/rollback.sh
```

Substitute the actual backup directory from the publisher output; do not run an invented path. The rollback restores the ten prior frontend assets or removes an asset that did not previously exist. Recheck the four browser routes and live cards. The earlier manual dashboard recovery backups are separate from publisher backups.

## Read-only health and freshness checks
```bash
systemctl is-active edge1-operations-private-web.service
systemctl is-active edge1-core-observation.timer
systemctl is-active edge1-crowdsec-observation.timer
systemctl is-active edge1-network-defense-observation.timer
systemctl is-active edge1-security-correlation-observation.timer
curl -fsS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8098/edge1-status/
curl -fsS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8098/edge1-status/security/
curl -fsS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8098/edge1-status/security/correlation.html
curl -fsS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8098/edge1-status/network-defense/
```

Collectors write read-only sanitized snapshots under `/var/www/edge1-status/`: `core-status.json`, `crowdsec-status.json`, `security-correlation.json`, and `network-defense/data/network-defense.json`. Check schema, generation timestamp, explicit availability/state and provenance for each snapshot. Core/CrowdSec/Network Defense/Correlation observation timers were configured for a roughly two-minute cadence at acceptance; a running timer is not evidence of a fresh successful snapshot. A 404 from an obsolete legacy endpoint should not be presented as a working subsystem. Browser JavaScript rendering, HTTP content and data freshness are independent checks.

To inspect units without modifying them:
```bash
systemctl status --no-pager edge1-core-observation.timer edge1-crowdsec-observation.timer edge1-network-defense-observation.timer edge1-security-correlation-observation.timer
journalctl -u edge1-core-observation.service -n 30 --no-pager
```

Avoid printing full private firewall/security data into public issues; redact source addresses, internal identifiers and sensitive logs. The public repository contains source and sanitized documentation, not runtime snapshots or private operational evidence.

## Accepted verification and handoff
- GitHub PR #592 squash-merged; local `main` fast-forwarded to `91096067` after exact-match backups of 13 root-owned obstructing files.
- Frontend deployment-parity audit: 10/10 matches; browser acceptance: 6/6; all four private routes HTTP 200; web unit and four timers active.
- Dedicated repo-specific SSH deploy key configured on Edge1 for Git access. **Never archive or commit the private key.**
- Release review verified four Python collector AST parses, nine systemd unit definitions and no matches from a targeted secret-pattern check; this was not an exhaustive security audit.
- Production CrowdSec acceptance and recovery remain separately documented in `docs/security/` and the restricted private Edge1 workspace.

## Next phases (not yet accepted)
1. Add automated CI tests for navigation-route parity, unified-publisher ten-asset preflight, rollback in a disposable fixture and collector schema contracts; never run production deployment in CI.
2. Improve live-data provenance, per-panel freshness and explicit unavailable states; retire legacy fetches safely without inventing telemetry.
3. Assess separately staged modules and browser security boundaries one module at a time; only mark `accepted_live` after independent route and visual acceptance.
4. Run controlled deployment/rollback rehearsal in staging before the next production frontend update.
