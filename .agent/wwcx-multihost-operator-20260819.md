# WW.CX Multi-Host Operator — 2026-08-19 Handoff

Status: Business159 website deployment path is live/accepted; bounded Business159 MCP source is merged but connector attachment and MCP-level live acceptance remain pending.

## Discovery

- Edge1 ordinary bounded status contract is the existing 16 zero-argument `edge1.*` tools.
- The MCP also has separate `agent.turn.status` and bounded-write `agent.turn.handoff` coordination tools; they must not be conflated with ordinary host-status routing.
- The existing Edge1 documentation-only filesystem controller remains intentionally scope-limited and was not broadened.
- No direct `edge1.*` MCP connector was attached to the implementing ChatGPT session, so no fresh live Edge1 operator call is claimed by this work.
- Business159 deployment source remains `johnkaminski727-alt/ww-cx-website`; the operator wraps that implementation instead of replacing it.
- The Business159 Operations Center consumer defaults to `/home/wwcxjywl/wwcx-store-private/operations-center/latest.json` and already supports receiver-side checksum verification plus configured HMAC mode.

## Multi-host operator source

PR #451 — Build bounded Business159 and WW.CX multi-host operators — is merged.

Implemented source includes:

- `tools/mcp/business159-live-shell/` bounded shared-host MCP package;
- 16 named parameterless Business159 read-only status tools;
- guarded connectivity/inspection tools;
- deployment wrapper with dry-run default, apply feature gate, clean-checkout requirement, exact expected commit, and post-deploy HTTP verification;
- staged public-root file controller: stage/status/diff/approve/apply/rollback with stage-local backups, SHA-256 verification, file-level atomic rename, explicit path/content restrictions, and audit records;
- raw account-level shell escape hatch disabled by default;
- eight source-controlled Skills for Business159 routing/shell/filesystem/authenticated/web, shared-host security, cross-host diagnosis, and WW.CX releases;
- CI workflow, static contract validator, and architecture documentation.

Repository validation for the substantive implementation passed:

- `Business159 Operator Connector`: success;
- `Edge1 Operator Validation`: success;
- `Validate repository`: success.

## Business159 website deployment — live / accepted

Host/principal verified on 2026-08-19:

```text
business159.web-hosting.com
wwcxjywl
```

Live document-root invariant verified before and after deployment:

```text
/home/wwcxjywl/public_html owner=wwcxjywl group=nobody mode=0750
```

The first exact whole-tree dry run exposed that historical `rsync --delete` semantics would have deleted independently managed host/runtime material including top-level `ops/`, `.well-known/`, runtime/admin backup files, and other non-release-owned content. No production apply occurred under that unsafe model.

The deployment model was then changed to release-owned synchronization:

- whole-document-root `--delete` is forbidden;
- only files/symlinks owned by the previous immutable release may be retired;
- live managed drift fails closed;
- unmanaged path collisions fail closed;
- host-only files survive deploy and rollback;
- source-to-live updates use checksum comparison so equal size/mtime cannot hide changed content;
- `.release-commit` remains immutable-release metadata and is excluded from normal public synchronization.

Website PRs merged during the acceptance sequence:

- #81 — exact dry-run synchronization behavior;
- #82 — release-owned synchronization preserving host-only files;
- #83 — proof-based cleanup of legacy public `.release-commit` metadata;
- #84 — remove temporary `sh -x` CI trace after managed-sync debugging; validation behavior unchanged.

### Accepted production release sequence

First hardened production deploy:

```text
commit=7a9aa88eaa48622010a4de06022a59c9fa92311f
release=/home/wwcxjywl/releases/ww-cx-website/20260819T200234Z
backup=/home/wwcxjywl/shared/ww-cx-website/backups/public-html-20260819T200234Z.tar.gz
healthcheck=https://ww.cx/ -> OK
```

That deployment changed only the intended managed file `admin/edge1-security-login.php`. Final acceptance then detected a legacy public `.release-commit` left by the old deployment model. The public marker contained:

```text
a3b4ab0e2717e704b56d85aac5051e45ebe09da7
```

and exact retained-release provenance was found at:

```text
/home/wwcxjywl/releases/ww-cx-website/20260819T185948Z
```

PR #83 added fail-closed migration cleanup: a public `.release-commit` may be removed only when exact content matches a canonical retained immutable release below the approved release root; otherwise synchronization reports `release_metadata_conflict` and stops before writes.

Final accepted remediation/deploy:

```text
commit=01ee93cf0337006c5d44031a5f9eb1a83e1d0100
release=/home/wwcxjywl/releases/ww-cx-website/20260819T201010Z
backup=/home/wwcxjywl/shared/ww-cx-website/backups/public-html-20260819T201010Z.tar.gz
managed action=*managed-metadata-delete .release-commit owner=/home/wwcxjywl/releases/ww-cx-website/20260819T185948Z
healthcheck=https://ww.cx/ -> OK
```

Post-apply acceptance verified:

- public `.release-commit` absent;
- `shared/current` points to `20260819T201010Z`;
- immutable release marker equals `01ee93cf0337006c5d44031a5f9eb1a83e1d0100`;
- document-root owner/group/mode remained exact;
- top-level host-only `ops/` tree digest unchanged;
- host-only `.well-known/` tree digest unchanged;
- host-side admin backup count unchanged at 18;
- managed `admin/edge1-security-login.php` matches the new immutable release;
- dedicated website checkout clean on `main` and synchronized with `origin/main`;
- public `https://ww.cx/` returned HTTP/2 200.

The website deployment path is therefore **LIVE / ACCEPTED** under the release-owned synchronization model. Do not revert to whole-document-root `rsync --delete`.

## Remaining Business159 operator acceptance gates

1. Install/attach `business159-live-shell` through an approved MCP connector mechanism.
2. Run `business159_connection_test`, then the 16 read-only tools against the real account.
3. Verify discovered hostname/principal/path assumptions and adjust environment configuration rather than hardcoding divergent live facts.
4. Run a disposable staged-filesystem smoke test through stage -> diff -> approve -> apply -> verify -> rollback -> verify rollback.
5. Do not enable raw shell merely for acceptance.
6. Do not mark the custom Business159 MCP operator itself live until connector attachment and live MCP tests succeed.
7. A direct `edge1.*` connector also remains absent from this ChatGPT session; no fresh live Edge1 read-only acceptance is claimed here.

## Skill/package continuation

The eight Business159/cross-host Skills are source-controlled and were formally validated/packaged on 2026-08-19 using the Skill Creator validation rules. Each bundle contains the required `SKILL.md` and `agents/openai.yaml`, the frontmatter validator passed, the OpenAI metadata YAML parsed with the required interface/dependencies/policy sections, and one upload-ready `skill.zip` was produced per Skill.

Validated packages:

- `business159-authenticated-operator`
- `business159-filesystem-operator`
- `business159-operator-router`
- `business159-shell-operator`
- `business159-web-operator`
- `shared-host-security-auditor`
- `wwcx-cross-host-operator`
- `wwcx-release-operator`

Packaging success alone is not installation. However, user-provided ChatGPT UI evidence on 2026-08-19 now verifies that **`business159-authenticated-operator` has been installed and is being invoked by ChatGPT in at least one supported runtime**. In that runtime, Skill invocation and dependency inspection succeeded, but the declared `business159-live-shell` MCP dependency was unavailable. The attempted Business159 staged smoke test therefore stopped at the connector preflight without running host commands or changing files.

Do not generalize that evidence to the other seven Skills until each is independently observed installed/active, and do not describe the Business159 MCP operator itself as live until `business159-live-shell` is attached and its live acceptance tests pass.

## Security stop conditions

No credentials or secret values in Git/chat/evidence. No DNS/firewall/certificate/authentication changes. No unrestricted filesystem authority. No destructive deletion outside reviewed rollback semantics. No force push/history rewrite. No production calling/messaging or emergency-service activation. Keep Edge1 and Business159 privilege models separate.
