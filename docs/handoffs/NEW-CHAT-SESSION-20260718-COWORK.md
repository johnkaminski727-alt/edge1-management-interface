# New Chat Starter: Cowork Session 2026-07-18 Handoff

Continue Edge1 management interface work from the 2026-07-18 Cowork session.

## What this session completed

1. Managed search service (MERGED to main via PR #1): systemd unit,
   installer, smoke test, runbook, register, asset validation test.
2. Branch prune (EXECUTED with operator approval): 14 merged/superseded
   remote branches deleted; see
   `registers/branch-triage-register-20260718.md` for the full record.

## Open PRs awaiting operator review (all current with main, CI-clean)

| Branch | Contents |
| --- | --- |
| `feature/vpn-route-prep` | Approval-gated VPN route: nginx template (basic auth, GET/HEAD only, IPv4-only), gated installer, credential helper, smoke test, runbook, register. Nothing active until installed on Edge1 with the approval flag. |
| `chore/branch-triage-and-adoption` | Branch triage register; adopts smoke-test `REQUIRE_LIVE_DIRECT` hardening and the release-docs index/checklist; adds the six missing controlled release documents plus `tests/validate_release_docs.py`. |
| `feature/operator-tools` | Roadmap items: `bin/validate-repo` unified validation entry point; `tools/operator/edge1-health-summary.py` read-only health snapshot; validation test. |

## After those PRs merge

```bash
git push origin --delete agent/big-bird-library agent/release-engineering-foundation
```

(Their unique content is adopted by the triage branch; originals retained
until merge per the triage register.)

## Pending operator actions on Edge1 (cannot be done from a cloud session)

1. `git pull` in `/opt/edge1-management-interface`.
2. Install + smoke-test the managed search service (service register
   20260718, "Operator Next Actions"); record the observed mode
   (expect `live_direct`).
3. Decide VPN route exposure; if approved, follow the route register.
4. Spamhaus secret rotation (Spamhaus register, pending row).
5. Record final backup artifact path/SHA-256 (handoff register item 4).

## Watch item

An empty branch `agent/complete-release-governance` appeared near session
end at the main SHA — possibly another session about to duplicate the
release documentation completed on the triage branch. Merge the triage PR
first, or point that session at it.

## Session access note

This session pushed via a fine-grained PAT (repo-scoped, Contents
read/write) supplied by the operator in-chat. The token copy lives only in
the archived session's workspace; revoke it in GitHub settings, or issue a
fresh one for the next session.
