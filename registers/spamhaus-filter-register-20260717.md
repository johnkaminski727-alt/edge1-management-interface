# Spamhaus Filter Register - 2026-07-17

| Item | Status | Evidence |
| --- | --- | --- |
| Update script | Ready | `tools/networking/spamhaus-nft-update.sh` |
| Installer | Ready | `tools/networking/install-spamhaus-filter.sh` |
| Smoke test | Ready | `tools/networking/spamhaus-filter-smoke-test.sh` |
| Systemd service | Ready | `tools/networking/systemd/bigbird-spamhaus-filter.service` |
| Systemd timer | Ready | `tools/networking/systemd/bigbird-spamhaus-filter.timer` |
| Operator runbook | Ready | `docs/handoff/spamhaus-filter-runbook.md` |

## Operational Target

Edge1 should maintain an nftables table named `inet bigbird_spamhaus` populated
from Spamhaus DROP and EDROP lists, refreshed by systemd every six hours.
