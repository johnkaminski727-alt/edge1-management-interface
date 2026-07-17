# Spamhaus Filter Register - 2026-07-17

| Item | Status | Evidence |
| --- | --- | --- |
| Update script | Complete | `tools/networking/spamhaus-nft-update.sh` |
| CIDR interval collapse fix | Complete | Commit `bc17cdd` |
| Installer | Complete | `tools/networking/install-spamhaus-filter.sh` |
| Smoke test | Complete | `tools/networking/spamhaus-filter-smoke-test.sh` |
| Status pusher | Complete | `tools/networking/push-spamhaus-status.sh` |
| Systemd service | Complete | `bigbird-spamhaus-filter.service`, last result `success` |
| Systemd timer | Complete | `bigbird-spamhaus-filter.timer`, state `active` |
| Shared-host database/API | Complete | `network_blocklist_*` tables and `ww.cx` endpoint readback |
| Operator runbook | Complete | `docs/handoff/spamhaus-filter-runbook.md` |
| Completion handoff | Complete | `docs/handoff/spamhaus-filter-completion-handoff.md` |
| Archive checklist | Complete | `docs/handoff/spamhaus-filter-archive-checklist.md` |
| Secret rotation | Pending | Rotate DB password and bearer token after archive acceptance |

## Final Verified Status

| Field | Value |
| --- | --- |
| `source_key` | `edge1_spamhaus` |
| `state` | `ok` |
| `drop4_count` | `1576` |
| `edrop4_count` | `0` |
| `combined4_count` | `1576` |
| `drop6_count` | `87` |
| `service_state` | `success` |
| `timer_state` | `active` |

## Repository Evidence

| Commit | Description |
| --- | --- |
| `0693b02` | Add Edge1 Spamhaus network filter |
| `bc17cdd` | Collapse Spamhaus nftables intervals |

## Operational Target

Edge1 maintains an nftables table named `inet bigbird_spamhaus`, populated from
Spamhaus DROP data and refreshed by systemd every six hours. Live status is
pushed to the `ww.cx` shared-host status endpoint for dashboard and archive
visibility.
