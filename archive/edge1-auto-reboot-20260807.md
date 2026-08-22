# Edge1 Temporary Auto Reboot Rollout Archive

Date: 2026-08-07
Host: `edge1.ww.cx`

> Historical evidence record. This document describes the state validated on 2026-08-07. It does not assert that the same schedule or files are still active on 2026-08-22 or later; current live state must be re-verified before operational decisions.

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

Confirmed at the time of the rollout:

- `/etc/cron.d/edge1-auto-reboot` ownership: `root:root`
- Permissions: `0644`
- Exact cron file SHA-256:

```text
27ad5a00229f3c7ed7afa707fb043c2bfb86946f84b9a184224df5cf47b53017
```

- Cron daemon restarted successfully.
- `edge1-scheduled-reboot --check` reported ACTIVE.
- No cron syntax errors were observed.

## Remaining observation recorded at rollout

After the first scheduled reboot, the original rollout called for verification with:

```sh
uptime
last reboot | head -5
journalctl -t edge1-auto-reboot
```

This archive entry does not promote that historical observation step into evidence of current state.

## Rollback documented at rollout

The documented rollback was to move the cron file out of `/etc/cron.d/` while retaining the archived backup.

Any present-day rollback or schedule change must first verify the current file, service, ownership, schedule, and related operational dependencies rather than assuming the 2026-08-07 state still applies.
