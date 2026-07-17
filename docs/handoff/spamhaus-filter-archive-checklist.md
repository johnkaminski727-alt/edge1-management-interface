# Spamhaus Filter Archive Checklist

Use this checklist before closing the Big Bird Networking / Spamhaus workstream.

| Step | Status | Command or Evidence |
| --- | --- | --- |
| Repository clean | Required | `git status --short` |
| Latest commits pushed | Done | `bc17cdd` on `origin/main` |
| nftables table present | Done | `sudo nft list table inet bigbird_spamhaus` |
| Service last result success | Done | `systemctl show -p Result --value bigbird-spamhaus-filter.service` |
| Timer active | Done | `systemctl is-active bigbird-spamhaus-filter.timer` |
| Summary file present | Done | `/var/lib/bigbird-networking/spamhaus/summary.txt` |
| ww.cx readback OK | Done | `state: ok`, counts non-zero |
| Runbook updated | Done | `docs/handoff/spamhaus-filter-runbook.md` |
| Completion handoff added | Done | `docs/handoff/spamhaus-filter-completion-handoff.md` |
| Register updated | Done | `registers/spamhaus-filter-register-20260717.md` |
| Secrets rotated | Pending | Rotate after archive handoff is accepted |

## Final Archive Command

From Edge1:

```bash
cd /opt/edge1-management-interface
git status -sb
git log --oneline -8
sudo tools/networking/spamhaus-filter-smoke-test.sh
bash tools/networking/push-spamhaus-status.sh
```

Record the readback output with non-zero counts in the operator archive.
