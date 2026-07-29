# Spamhaus Live-State Deployment Note

Date: 2026-07-29
Status: live installer acceptance passed; exact accepted state pending evidence-summary readback

The read-only Spamhaus live-state installer completed successfully on Edge1.

Evidence:

```text
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180755Z
```

The deployment reported no nftables, firewall, DNS, routing, Fail2ban, proxy, or traffic-control changes.

The exact accepted state (`active_verified`, `partial`, `not_present`, or `unavailable`) was not included in the final terminal excerpt. Read it from `acceptance-summary.json` in the evidence directory before making a specific enforcement claim.
