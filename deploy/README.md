# Deployment Notes

Target repo path recommendation:

`/opt/edge1-management-interface`

Initial deployment should be source-only. Do not expose the website publicly.

Required deployment properties:

- private/VPN-only
- authenticated operator access
- read-only first
- no secrets committed to git
- no binary archive files committed to git

## Time Authority readiness

The Time Authority deployment includes non-mutating preflight checks and post-install smoke tests:

```bash
deploy/time-authority-edge1-preflight.sh
sudo deploy/install-time-authority-edge1.sh
deploy/install-time-authority-shared-host.sh
```

The shared-host installer supports Python 3.6+, installs its cron entry idempotently, and preserves collected JSONL data during rollback.
