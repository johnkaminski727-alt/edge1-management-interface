# Edge1 Operator Shell handoff

Updated: 2026-08-20

## Repository state

- Objective: issue #476, continuing navigation provenance from #59 without promoting the CX Admin discovery registry.
- Implementation PR: #480.
- Merge commit: `4f77ebcde44df940390e5d03dc5af1872211faf9`.
- Canonical registry: `config/edge1_operator/navigation_registry.json`.
- Architecture/runbook: `docs/operations/edge1-operator-shell.md`.
- Exact PR head accepted by CI: `ae7a59446904ce68c42636fc23364ae9f8b7654f`.
- Exact-head workflows passed: repository validation, Edge1 Operator Validation, Unified Communications Validation, Edge1 Operator Shell.

## Safety state

- Navigation grants no authorization.
- Generic execution is unauthorized.
- Production communications traffic is unauthorized.
- Operations API mutations remain disabled.
- Unknown status must not render as healthy.
- Store Admin remains outside this shell.
- WW.CX AI browser navigation remains gated until browser acceptance is verified.

## Live pre-deployment evidence

The post-merge bounded Operator check found:

- Edge1 Operator MCP healthy;
- Operations API healthy, loopback, mutations disabled;
- management repository detached at `d326d4546abefa695a293266342a5c1075f010e2` rather than current GitHub `main`;
- Apache active/running;
- `wwcx-communications-workspace.service` active/running;
- Communications workspace still loopback-only on `127.0.0.1:8095`;
- BigBird gateway healthy in read-only mode at 0.3.5-alpha.1.

The live checkout has therefore not yet received the shell merge. Do not claim live publication or browser acceptance until the checkout is deliberately advanced and the deployment/rollback checks in the runbook are completed.

Two BigBird Edge1 connector lifecycle units were observed failed during the same bounded service snapshot. They are outside the Operator Shell deployment scope; do not fold their remediation into this deployment without a separate diagnosis/scope decision.

## Next action

Use an authenticated Edge1 execution path to:

1. capture the current live commit and clean-state evidence;
2. advance the live checkout to the intended current `main` commit without force/history rewriting;
3. run repository/shell preflight validation;
4. run the Operations Center publisher dry-run, then `--apply` and retain its timestamped rollback artifact;
5. re-run the existing Communications workspace installer so the running loopback service picks up the merged server/page/assets, preserving its built-in rollback and mutation/listener checks;
6. do not activate an unverified Security Console or WW.CX AI public route as a side effect;
7. verify Apache, Operations API, Communications service, listener exposure, and mutation-disabled state;
8. perform authenticated browser acceptance for desktop/narrow/keyboard and protected Security behavior where the route is actually accepted;
9. record sanitized acceptance evidence and exact rollback locations here or in a dated operations record.

If only the bounded read-only Edge1 Operator is available, stop at this execution boundary and provide one attended operator paste box rather than inventing live results.
