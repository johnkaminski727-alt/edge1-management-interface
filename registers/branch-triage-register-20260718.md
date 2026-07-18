# Branch Triage Register - 2026-07-18

Triage of all remote branches against `main` at `7405033`. "Merged" means
every commit is already reachable from main; "superseded" means main
contains a newer evolution of the same content and the branch adds nothing.

## Adopted by this triage (branch `chore/branch-triage-and-adoption`)

| Branch | What was adopted |
| --- | --- |
| `agent/big-bird-library` | `REQUIRE_LIVE_DIRECT=1` hardening for the service smoke test (cherry-picked, original authorship preserved) |
| `agent/release-engineering-foundation` | `docs/release/README.md` and `docs/release/release-checklist.md` (merged); the six further controlled documents its index referenced did not exist anywhere and were written to complete the set |

## Active branches — keep

| Branch | Status |
| --- | --- |
| `feature/vpn-route-prep` | Awaiting review/merge (approval-gated VPN route assets; current with main) |
| `chore/branch-triage-and-adoption` | This triage; awaiting review/merge |

## Prune candidates — fully merged into main (0 unmerged commits)

| Branch |
| --- |
| `agent/add-time-authority-monitoring` |
| `agent/digital-preservation-standard-v1` |
| `agent/time-authority-python36-compat` |
| `agent/time-authority-readiness-sweep` |
| `agent/time-authority-rollout-simulation` |
| `docs/citation-and-contributing` |
| `docs/records-evidence-baseline` |
| `records-evidence-automation-v2` |
| `wwcx-preservation-framework-rollout` |

## Prune candidates — superseded iterations (main carries the newer version)

| Branch | Superseded by |
| --- | --- |
| `records-evidence-automation` | `records-evidence-automation-v2` (merged via PR #12) |
| `ci/records-evidence-baseline` | main's `.github/workflows/validate.yml` and merged records-governance docs |
| `docs/community-and-roadmap` | `CONTRIBUTING.md` / `ROADMAP.md` on main (identical content) |
| `docs/public-project-presentation` | All five files exist on main; only drift is an older README revision |
| `agent/big-bird-library` | After its single commit is adopted via this triage |
| `agent/release-engineering-foundation` | After its two docs are adopted via this triage |

## Deletion commands (operator-run, after adopting branch is merged)

Branch deletion is destructive, so it is left to the operator:

```bash
git push origin --delete \
  agent/add-time-authority-monitoring \
  agent/digital-preservation-standard-v1 \
  agent/time-authority-python36-compat \
  agent/time-authority-readiness-sweep \
  agent/time-authority-rollout-simulation \
  docs/citation-and-contributing \
  docs/records-evidence-baseline \
  records-evidence-automation-v2 \
  wwcx-preservation-framework-rollout \
  records-evidence-automation \
  ci/records-evidence-baseline \
  docs/community-and-roadmap \
  docs/public-project-presentation \
  agent/big-bird-library \
  agent/release-engineering-foundation
```

Verification used for every "merged/superseded" call: `git cherry` patch
equivalence plus per-file content comparison against main.
