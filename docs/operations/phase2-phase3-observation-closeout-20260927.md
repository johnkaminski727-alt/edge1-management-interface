# Edge1 Unified Operations Center — Phase 2 and Phase 3 observation closeout (2026-09-27)

**Status:** Phase 2 frontend deployed and operator browser-accepted; Phase 3 Fail2ban and nftables read-only telemetry deployed, recurring execution verified, and browser-accepted for visible source states. This document is dated acceptance evidence, **not a current-health guarantee**. Existing baseline runbook: `docs/operations/unified-operations-center-runbook-20260927.md`; existing release register: `registers/unified-operations-center-release-20260927.md`.

## Phase 2 — frontend release

- Release: `7fe9999fe55b76abafc624698bc88b9c876e4dac` (PR #599), following merged work in PRs #594–#598. Local `main` synchronized and clean at predeployment; current frontend source/runtime parity was **10/10 assets** after publishing.
- Approved runtime: `/var/www/edge1-status`, served only through private loopback `127.0.0.1:8098`; all four private browser routes returned HTTP 200 and the private web service plus four foundational observation timers were active.
- Updated UI: continuously advancing freshness displays and stale/expired observation handling in Operations Center, CrowdSec, Security Correlation and Network Defense. Missing historical Suricata data is marked **not deployed** rather than repeatedly polled as a presumed working source. Correlation source availability is not proof of cross-source correlation; source freshness is not a packet/event-recency test.
- Full prepublication snapshot backup: `/var/backups/edge1-phase2-195b-20260927T065821Z`. Publisher rollback: `/var/backups/edge1-unified-publish-20260927T065907Z/rollback.sh`. Inspect the corresponding backup manifest before rollback; the backups are on Edge1, not in Git.
- Acceptance: ten deployed assets byte-for-byte matched source; four private routes HTTP 200; all four read-only JSON snapshots were 43 seconds old at production verification; operator confirmed four-page browser acceptance. No production collector, firewall, DNS or public-listener change in this frontend deployment.

## Phase 3 — Fail2ban and nftables observability

**Repository verifiers already present:** `server/fail2ban_live_state_verifier.py`, `server/nftables_live_state_verifier.py`, `server/spamhaus_live_state_verifier.py`. Existing Network Defense exporters consume sanitized verifiers' JSON; no new network enforcement is provided by this integration.

### Discovery and isolated validation

- Before installation, `fail2ban.service`, `crowdsec.service`, `crowdsec-firewall-bouncer.service`, `ufw.service` and `unbound.service` were active. `nftables.service` was inactive and disabled, **which does not prove the live kernel ruleset empty**.
- Isolated Fail2ban verifier returned `active_observed`, reachable control socket and **1/1 jails observed**; `enforcement_verified=false`.
- Isolated nftables aggregate verifier returned `ruleset_observed`, **5 tables, 75 chains and 191 rules**, `enforcement_verified=false`. Full ruleset and address details were not published.
- Spamhaus dedicated table was absent, its updater service/timer were `not-found`, and the isolated verifier returned `unavailable`; no Spamhaus activation or new filtering was performed.
- End-to-end temporary Network Defense export accepted both new sources as current, while retaining Spamhaus unavailable and zero new enforcement-verification claims. Its temporary 3/9 source and 2/7 observed-layer counts were **not production counts**.

### Production deployment and verification

- Installed existing read-only units from `deploy/systemd/`:
  - `wwcx-fail2ban-live-state.service` and `wwcx-fail2ban-live-state.timer`
  - `wwcx-nftables-live-state.service` and `wwcx-nftables-live-state.timer`
- Both timers enabled and active, configured in repo for approximately 60-second cadence. Sanitized evidence:
  - `/var/lib/bigbird-security/fail2ban/live-state.json`
  - `/var/lib/bigbird-networking/nftables/live-state.json`
- Independent deployment backup: `/var/backups/edge1-phase3-201-20260927T070518Z`; contains the preintegration Network Defense snapshot. Review the installed units and backup before executing any future removal or rollback.
- Production Network Defense refreshed: **5/11 sources available**, **7/11 layers observed**, **0 verified enforcement claims** at acceptance. These counts represent observability coverage, not security effectiveness.
- Both systemd timers subsequently triggered at **2026-09-27 07:06:26 UTC**, after their initial deployment triggers. Both JSON observations were **51 seconds old** at recurring-run validation; both sources remained available and nonstale in published Network Defense. The private dashboard JSON returned HTTP 200.
- Operator-supplied Chrome screenshot (approximately 07:08 local browser view) visibly confirmed `FAIL2BAN LIVE STATE: Observed`, `NFTABLES LIVE STATE: Observed`, `SPAMHAUS: Not connected`, `SPAMHAUS LIVE STATE: Not connected`, and `DNS POLICY: Not staged`. The page itself labels these source statuses as exporter-reported, not independently verified by the browser.

### Operational limits and next work

- **No change** to live firewall rules, nftables service state, Fail2ban jails, DNS policy, public listeners, or Spamhaus deployment was made by the observation assignments.
- Do not mark Spamhaus, historical Suricata, legacy Network/Operations feeds, or DNS policy as live because the new Fail2ban/nftables feeds are functioning. The observed DNS service states do not establish independently verified resolver success.
- Keep source availability separate from source freshness, service state and verified packet-level enforcement. The Network Defense frontend is a read-only status surface.
- Next separately scoped work: assess missing feeds and optionally stage Spamhaus/DNS changes under distinct approval, backup and rollback gates. Do not enable filtering or firewall-control services as a side effect of observability work.

## Read-only follow-up checks on Edge1

```bash
systemctl is-active wwcx-fail2ban-live-state.timer wwcx-nftables-live-state.timer
systemctl show wwcx-fail2ban-live-state.service wwcx-nftables-live-state.service --property=Result,ExecMainStatus --no-pager
systemctl show wwcx-fail2ban-live-state.timer wwcx-nftables-live-state.timer --property=LastTriggerUSec --no-pager
curl -fsS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8098/edge1-status/network-defense/data/network-defense.json
```

Do not paste raw `nft list ruleset`, banned addresses, raw security records, sensitive system journals or credentials into public issues. This closeout contains only accepted sanitized counts, service states and file paths.
