# Edge1 Temporary Auto Reboot Rollout Archive

Date: 2026-08-07
Host: `edge1.ww.cx`

## Completed

Installed a temporary automatic reboot schedule for Edge1:

- Cadence: every 12 hours
- Schedule: `00:40 UTC` and `12:40 UTC`
- Expiry: `2027-02-07 00:40 UTC`
- Timezone: UTC
- Cron service: active
- Controller: `/usr/local/sbin/edge1-scheduled-reboot`
- Schedule file: `/etc/cron.d/edge1-auto-reboot`

## Validation

Confirmed:

- `/etc/cron.d/edge1-auto-reboot` ownership: `root:root`
- Permissions: `0644`
- Exact cron file SHA-256:

```
27ad5a00229f3c7ed7afa707fb043c2bfb86946f84b9a184224df5cf47b53017
```

- Cron daemon restarted successfully.
- `edge1-scheduled-reboot --check` reports ACTIVE.
- No cron syntax errors observed.

## Remaining observation

After the first scheduled reboot, verify:

```
uptime
last reboot | head -5
journalctl -t edge1-auto-reboot
```

## Rollback

Disable by moving the cron file out of `/etc/cron.d/` and retaining the archived backup.
