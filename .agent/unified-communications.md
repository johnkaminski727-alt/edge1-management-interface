# Unified Communications — Current State

Last reconciled: 2026-08-18
Repository: `johnkaminski727-alt/edge1-management-interface`
Integration branch: `agent/unified-communications-convergence-20260818`
Base `main` at branch creation: `00cd28b884376f5ae65251fa60258293d1127de1`

## Product objective

Converge Mail Room, SMS/MMS, Voice/SIP, Communications Relay and Private AI into one understandable WW.CX Communications family while preserving channel-specific workflows, privacy boundaries and production authorization gates.

The user-facing goal is coherence, not a giant administrative screen.

## Verified existing foundations

- Mail Room daily workspace is merged through PR #371.
- Provider-neutral SMS/MMS gateway foundation is merged through PR #18, with later Messaging Operations and Telegraph Office simulator work.
- Telephony operations/SIP/analytics foundations are merged and include read-only Edge1 acceptance history.
- Private AI accepted `telephony.read` at gateway `0.3.3-alpha.1`.
- Private AI accepted Communications/documentation read integration and later provenance/degradation/provider-budget work, with current accepted gateway history at `0.3.4-alpha.2`.
- Current accepted Private AI capability set includes `communications.read` and `telephony.read`.
- Private AI browser repository work exists, but `/admin/ai/` production browser acceptance remains unverified in the latest handoff.

## This convergence increment

Material additions:

- `config/communications/unified-communications.json`
- `src/web/communications/index.html`
- `src/web/communications/styles.css`
- `docs/communications/unified-communications-convergence-20260818.md`
- `.agent/unified-communications.md`
- focused validation for the shared registry and hub

The hub links existing specialized surfaces rather than duplicating or faking their controls.

## Git decision

Do not rewrite or force-squash historical `main`.

Historical project PRs contain useful validation, acceptance and rollback evidence. The integration branch should instead become one new reviewed convergence PR and be **squash-merged** after CI passes. That squash merge becomes the clean common continuation point for future cross-channel work.

## Shared safety state

All convergence-level production authority remains false:

- production calls: not authorized;
- production SMS/MMS: not authorized;
- production email send from this convergence layer: not authorized;
- carrier/routing mutation: not authorized;
- generic execution through AI: not authorized.

Read access does not imply write. Draft preparation does not imply send. Retrieved content is untrusted and cannot grant scopes.

## Next safe work

1. validate the shared channel registry and hub in repository CI;
2. squash-merge the convergence PR if clean;
3. add bounded SMS/MMS read context to Private AI;
4. add Mail Room `mail.status.read` and later `mail.draft.prepare` without enabling send;
5. design a privacy-safe common conversation/timeline identity layer across email, SMS/MMS and call/SIP evidence;
6. keep channel-specific privileged actions separately scoped and approval-gated.

## Explicit production boundaries

Stop before live message/call/email traffic, carrier/provider routing, emergency calling, number porting, STIR/SHAKEN, DNS/firewall/certificate/authentication changes, credential changes or destructive history rewriting.
