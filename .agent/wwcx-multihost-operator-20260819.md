# WW.CX Multi-Host Operator — 2026-08-19 Handoff

Status: repository implementation prepared; live connector acceptance pending.

## Discovery

- Edge1 ordinary bounded status contract is the existing 16 zero-argument `edge1.*` tools.
- The MCP also has separate `agent.turn.status` and bounded-write `agent.turn.handoff` coordination tools; they must not be conflated with ordinary host-status routing.
- The existing Edge1 documentation-only filesystem controller remains intentionally scope-limited and was not broadened.
- No direct `edge1.*` MCP connector was attached to the implementing ChatGPT session, so no new live Edge1 operator call is claimed by this work.
- Business159 deployment source remains `johnkaminski727-alt/ww-cx-website`; the operator wraps that implementation instead of replacing it.
- The Business159 Operations Center consumer defaults to `/home/wwcxjywl/wwcx-store-private/operations-center/latest.json` and already supports receiver-side checksum verification plus configured HMAC mode.

## Implemented on branch `agent/wwcx-multihost-operator-20260819`

- `tools/mcp/business159-live-shell/` bounded shared-host MCP package.
- 16 named parameterless Business159 read-only status tools.
- Guarded connectivity/inspection tools.
- Deployment wrapper with dry-run default, apply feature gate, clean-checkout requirement, exact expected commit, and post-deploy HTTP verification.
- Staged public-root file controller: stage/status/diff/approve/apply/rollback with stage-local backups, SHA-256 verification, file-level atomic rename, explicit path/content restrictions, and audit records.
- Raw account-level shell escape hatch disabled by default.
- Eight source-controlled Skills for Business159 routing/shell/filesystem/authenticated/web, shared-host security, cross-host diagnosis, and WW.CX releases.
- CI workflow and static contract validator.
- Architecture documentation.

## Separate `ww-cx-website` branch

Branch: `agent/business159-deployer-safety-20260819`.

Prepared hardening:

- refuse a dirty dedicated deploy checkout rather than resetting unknown work;
- fast-forward-only source update instead of `reset --hard`;
- exact `--delete` deployment synchronization;
- functional HTTPS verification before success;
- automatic invocation of the existing release rollback when verification fails and a previous release exists;
- rollback target constrained under the configured release root;
- rollback exact synchronization and document-root metadata verification;
- updated deployment tests/docs.

## Validation still required

1. Open PRs for both branches.
2. Require repository CI to pass at the exact final heads.
3. Install/attach `business159-live-shell` through the approved MCP connector mechanism.
4. Run `business159_connection_test`, then the 16 read-only tools against the real account.
5. Verify discovered hostname/principal/path assumptions and adjust environment configuration rather than hardcoding divergent live facts.
6. Run an explicitly safe disposable staged-filesystem smoke test through stage -> diff -> approve -> apply -> verify -> rollback -> verify rollback.
7. Do not enable raw shell merely for acceptance.
8. Do not mark the Business159 operator live until the connector and live tests succeed.

## Security stop conditions

No credentials or secret values in Git/chat/evidence. No DNS/firewall/certificate/authentication changes. No unrestricted filesystem authority. No destructive deletion outside stage-local rollback semantics. No force push/history rewrite. No production calling/messaging or emergency-service activation. Keep Edge1 and Business159 privilege models separate.
