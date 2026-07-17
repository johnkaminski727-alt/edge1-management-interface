# Edge1 Spamhaus Filter Completion Handoff

## Summary

Edge1 Spamhaus filtering is complete and operational.

The implementation installs a dedicated nftables table, refreshes Spamhaus data
through a systemd timer, validates generated nftables rules before applying
them, and reports live status to the `ww.cx` shared-host status endpoint.

## Completed Components

| Component | Status | Evidence |
| --- | --- | --- |
| nftables filter | Complete | `inet bigbird_spamhaus` exists |
| DROP/EDROP updater | Complete | `/usr/local/sbin/bigbird-spamhaus-nft-update` |
| CIDR overlap handling | Complete | `ipaddress.collapse_addresses(...)` |
| systemd service | Complete | `bigbird-spamhaus-filter.service` result `success` |
| systemd timer | Complete | `bigbird-spamhaus-filter.timer` active |
| shared-host DB/API | Complete | `https://ww.cx/api/network-manager-spamhaus-status.php` readback `ok` |
| repository commits | Complete | `0693b02`, `bc17cdd` on `origin/main` |

## Final Verified Readback

```json
{
  "source_key": "edge1_spamhaus",
  "state": "ok",
  "drop4_count": "1576",
  "edrop4_count": "0",
  "combined4_count": "1576",
  "drop6_count": "87",
  "service_state": "success",
  "timer_state": "active"
}
```

## Important Operational Detail

`bigbird-spamhaus-filter.service` is a `Type=oneshot` unit. A successful service
run returns to `inactive (dead)`. This is expected. The reliable service health
field is:

```bash
systemctl show -p Result --value bigbird-spamhaus-filter.service
```

## Archive State

Archive this handoff with:

- `docs/handoff/spamhaus-filter-runbook.md`
- `docs/handoff/spamhaus-filter-completion-handoff.md`
- `docs/handoff/spamhaus-filter-archive-checklist.md`
- `registers/spamhaus-filter-register-20260717.md`
- `tools/networking/push-spamhaus-status.sh`
- repository commits through `bc17cdd`

## Follow-Up

Rotate setup-exposed credentials after the archive is complete:

- `business159` MySQL user `wwcxjywl_nm`
- Network-manager bearer token in the private shared-host config

Do not store either secret in repository files or handoff documents.
