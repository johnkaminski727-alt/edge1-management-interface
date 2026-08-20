# Current State

Last reconciled: 2026-08-20  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Authoritative branch: `main`

This file is the concise cross-workstream continuation point. Historical details remain in dated acceptance/runbook records.

## Repository / public front door

The 2026-08-19 Edge1 public front-door cutover is LIVE / ACCEPTED and must not be reopened without fresh contrary evidence.

Accepted ordinary routing remains:

- raw/default IPv4 HTTP `/` -> `302 https://ww.cx/time/`;
- unmatched Host HTTP `/` -> same;
- `edge1.ww.cx` HTTP `/` -> existing `301 https://edge1.ww.cx/`;
- `edge1.ww.cx` HTTPS `/` and `/index.html` -> `302 https://ww.cx/time/`;
- `/edge1-status/` preserved;
- unknown/non-root paths preserved;
- raw HTTPS behavior not weakened;
- PBX/SIP named-host behavior preserved;
- Apache and chronyd listener ownership preserved.

Rollback evidence remains:

```text
/var/backups/wwcx-edge1-front-door-approved-20260819T052836Z
/var/backups/wwcx-edge1-front-door-approved-20260819T052836Z/rollback.sh
```

HTTP 302 is intentional. Any 308 promotion is future optional work.

## Repository continuation

PR #450 and hardening follow-up PR #452 are merged. The authenticated human operator advanced the clean Edge1 checkout through the reviewed systemd-boundary remediation head `d26b9f3e625f70c5aa5a9d29342a2537218f0f46` while leaving unrelated later runtime changes off the production checkout.

The first hardened Secure MCP preactivation validator run failed closed before doctor because `edge1-operator` could not traverse the then-service-account-owned `/etc/systemd/system`. That finding is now repaired and verified as described below. The Secure MCP tunnel remains inactive/disabled; the Operator and Big Bird tunnel remain active/enabled.

PR #462 finalized the remediation gate so it pins every required utility, the exact reviewed tunnel unit, and exact preactivation service states. The production repair itself was applied only after a clean dry run and explicit user approval.

## Attended operator handoff convention

WW.CX attended operator command blocks now follow `docs/operator-pastebox-convention.md` as a durable human-factors safety control.

When ChatGPT must hand a command to the human operator instead of executing it directly:

- show a visible `SERVER: <host> — <action>` or `WORKSTATION:` title above the paste box;
- begin the box with a `SERVER` / expected `USER` / `ACTION` / bounded `SCOPE` banner;
- use one host per paste box and assert the expected hostname before host mutation when practical;
- identify the command as operator-run / not yet executed by the assistant;
- explicitly state where the resulting output must be deposited, normally back into the current ChatGPT conversation, with stable start/end markers when practical.

Cross-host workflows use separate numbered paste boxes rather than ambiguous mixed-host blocks.

## Business159 / WW.CX public deployment

The Business159 website deployment path is **LIVE / ACCEPTED** as of 2026-08-19.

Verified live host/principal and document-root invariant:

```text
host=business159.web-hosting.com
principal=wwcxjywl
/home/wwcxjywl/public_html owner=wwcxjywl group=nobody mode=0750
```

The original whole-document-root deployment model was rejected after a dry run showed that `rsync --delete` would remove host-only operational/runtime content including `ops/`, `.well-known/`, and unrelated admin/runtime files. No production apply occurred under that unsafe model.

The accepted deployment model now scopes changes to immutable-release ownership, fails closed on managed drift and unmanaged collisions, preserves host-only content, uses checksum comparison for managed updates, and forbids whole-document-root `--delete`.

Website hardening PRs #81, #82, and #83 are merged. PR #84 removed the temporary `sh -x` trace retained during managed-sync debugging; both Business159 validation jobs passed and deployment behavior is unchanged. Final accepted public release:

```text
commit=01ee93cf0337006c5d44031a5f9eb1a83e1d0100
release=/home/wwcxjywl/releases/ww-cx-website/20260819T201010Z
backup=/home/wwcxjywl/shared/ww-cx-website/backups/public-html-20260819T201010Z.tar.gz
healthcheck=https://ww.cx/ -> HTTP 200
```

PR #83 also completed a one-time fail-closed migration cleanup for the legacy public `.release-commit`: the marker `a3b4ab0e2717e704b56d85aac5051e45ebe09da7` was removed only after exact retained-release provenance was verified at `/home/wwcxjywl/releases/ww-cx-website/20260819T185948Z`.

Post-apply acceptance verified:

- public `.release-commit` absent;
- `shared/current` points to the `20260819T201010Z` immutable release;
- release marker equals `01ee93cf0337006c5d44031a5f9eb1a83e1d0100`;
- document-root owner/group/mode unchanged;
- host-only `ops/` digest unchanged;
- host-only `.well-known/` digest unchanged;
- host-side admin backup count unchanged at 18;
- managed `admin/edge1-security-login.php` matches the immutable release;
- dedicated website checkout clean and synchronized with `origin/main`;
- `https://ww.cx/` returned HTTP/2 200.

Do not revert Business159 to whole-tree `rsync --delete`.

The source-controlled bounded `business159-live-shell` MCP is not yet attached in this ChatGPT runtime. MCP-level connection/read-only/staged-filesystem acceptance remains separate work; do not claim that custom MCP surface live until tested through an approved connector/runtime.

The eight Business159/cross-host Skills have now been formally validated and packaged with one upload-ready `skill.zip` per Skill. Each source bundle contains the required `SKILL.md` and `agents/openai.yaml`; Skill frontmatter validation passed and OpenAI metadata YAML parsed with the required interface/dependencies/policy sections. Packaging success is not installation: do not claim the Skills active until uploaded/installed in a supported ChatGPT runtime, and MCP-dependent Skills still require their declared connector dependencies.

## P0 security finding — global systemd unit-directory ownership

Status: **LIVE / REPAIRED / VERIFIED** on 2026-08-20.

The original read-only production inspection found the Edge1 tunnel unit itself correct but its parent directory unsafe:

```text
/etc/systemd/system owner=bigbird-time:bigbird-time mode=0750
/etc/systemd/system/edge1-secure-mcp-tunnel.service owner=root:root mode=0644
unit_sha256=a79a7ae19b2fb639c34a895c36b3ef3055a83b2342e037ddf60546cdda4d77dd
```

Root cause was the historical Time Authority installer assigning the service account to both its application data directory and the global systemd unit directory in one `install -d` command. Repository hardening corrected the installer/preflight and added a fail-closed remediation.

A dry run then matched the exact reviewed preconditions. After explicit production approval limited to this metadata repair, the authenticated human operator ran the reviewed remediation with `--apply`.

Protected evidence:

```text
/var/lib/wwcx-deployment-evidence/systemd-unit-dir-boundary/20260820T011819Z
```

Accepted post-apply state:

```text
/etc/systemd/system owner=root:root mode=0755
/etc/systemd/system/edge1-secure-mcp-tunnel.service owner=root:root mode=0644
unit_sha256=a79a7ae19b2fb639c34a895c36b3ef3055a83b2342e037ddf60546cdda4d77dd
edge1_operator_tunnel_unit_readable=yes
edge1-secure-mcp-tunnel active=inactive enabled=disabled
edge1-operator-mcp active=active enabled=enabled
bigbird-ai-tunnel active=active enabled=enabled
```

The remediation reported `service_state_changed=false`, `unit_contents_changed=false`, `EDGE1_SYSTEMD_UNIT_DIR_REPAIR=PASS`; the surrounding verifier exited `apply_wrapper_rc=0`. No service lifecycle command was run and no tunnel activation was requested.

Finding/acceptance record:

`docs/security/edge1-systemd-unit-dir-boundary-20260819.md`

## Edge1 Operator / Secure MCP Tunnel

The bounded server-side Operator remains accepted live:

- `edge1-operator-mcp.service` active/enabled;
- principal `edge1-operator`;
- MCP loopback `127.0.0.1:8102` only;
- Operations API loopback `127.0.0.1:8097` only;
- bearer boundary retained; unauthenticated MCP returns 401;
- reviewed contract is 16 named parameterless read-only tools;
- Operations API mutations remain disabled.

Secure MCP Tunnel staging and local credential provisioning are complete without exposing secret values:

- `/etc/edge1-tunnel/tunnel-id` exists as `root:edge1-operator` mode `0640` and is readable by `edge1-operator`;
- `/etc/edge1-tunnel/runtime-api-key` exists with the same restricted ownership/mode/readability;
- `/etc/edge1-operator/mcp-token` remains `edge1-operator:edge1-operator` mode `0600`;
- installed tunnel-client remains `0.0.10+105e17a79a36e4e5c897fd698ed2b8dbf935b144`, SHA-256 `937347720ef32ef3ef2f68f4496b2dd7917ca5e575452ed87a4ce78d0262a100`;
- `edge1-secure-mcp-tunnel.service` is disabled/inactive;
- `bigbird-ai-tunnel.service` remains active/enabled;
- no tunnel start/enable command has been run.

### Doctor compatibility

Raw doctor returned exit code 2 with exactly one failed check:

```text
FAILED_CHECKS oauth_metadata
HTTP 404 from http://127.0.0.1:8102/.well-known/oauth-protected-resource/mcp
```

This remains a reviewed old-build doctor compatibility issue, not a reason to add synthetic OAuth endpoints. PR #452 hardened the validator so it requires the exact reviewed binary/assets/metadata, bearer boundary behavior, OAuth 404-only compatibility case, and exact old-doctor result.

The filesystem trust-boundary blocker that prevented the hardened validator from reaching those checks is resolved. The next Edge1 host action is a **read-only rerun** of `deploy/edge1-tunnel/validate-edge1-secure-mcp-tunnel-doctor.sh`. Only a full `EDGE1_TUNNEL_COMPAT_DOCTOR=PASS` may advance to attended tunnel activation.

Starting `edge1-secure-mcp-tunnel.service` remains a separate explicit production/account-linked boundary. Persistence stays blocked until attended tunnel + ChatGPT acceptance succeeds.

No direct `edge1.*` MCP connector is attached to this ChatGPT session yet.

## Security-boundary inventory

The current read-only security-boundary inventory has run successfully on Edge1. Aggregate result:

```text
records=164
mapped=160
missing_known=0
unknown_preserved=4
filesystem_anomaly=1
```

Apache config testing passed. The inventory reported no live configuration/source-tree/traffic-control mutation and did not collect credentials/cookie values.

Remaining work is narrow: record the exact timestamped evidence directory and classify the four preserved unknowns plus one filesystem anomaly using path/mode/hash/relationship metadata only before any restricted-release/public-tree work proceeds.

DNS, firewall, certificates, authentication policy, listeners, and production traffic remain separately gated.

## Asterisk / alerting

The read-only warning follow-up is complete at the service/configuration level:

- Asterisk active;
- PJSIP transport configuration exists;
- Asterisk owns loopback UDP `127.0.0.1:5061`;
- SysV `S01asterisk` startup links exist in runlevels 2-5 and `systemctl is-enabled` reports enabled through the systemd-sysv wrapper;
- TCP `8089` is loopback-only;
- local TLS 1.3 handshake succeeds using the Edge1 certificate;
- audit produced zero failures.

No listener/firewall/certificate/SIP/startup-policy mutation is justified. PR #450 corrected the audit's systemd-sysv stderr handling; the corrected read-only audit still needs one final host rerun to retain the final warning/failure summary.

The offline CAP-CP/EBS laboratory remains isolated; no `Actual` alert delivery, calls/pages, tones, or public delivery path are authorized by this state.

## Control Surfaces

Fresh bounded diagnostics for summary/listeners/Asterisk/Kamailio/FreePBX completed. Native CLI diagnostics may be privilege-limited while passive fallback evidence succeeds and higher-level telephony health remains healthy. Do not widen permissions merely to make a diagnostic card green.

The prior general-inventory `rc=126` was a repository packaging issue: the file was mode `0644`, while interpreter execution succeeded and the filesystem is executable. PR #450 corrected `scripts/control-surfaces-live-inventory.sh` to Git mode `100755`; the Edge1 checkout has since fast-forwarded through that change. The executable read-only inventory still needs its final rerun and retained manifest/summary.

Existing FreePBX Admin/UCP private-source boundaries remain unchanged. Any temporary/private native-session mechanism remains separately gated.

## DTMF provider work

Externally blocked. Mailbox recheck on 2026-08-19 found no substantive provider technical answer after the 2026-08-14 notice that there was still no update.

Keep:

```text
response_state=pending
provider_reply_received=false
matrix_update_allowed=false
live_test_authorized=false
```

No live calls or DTMF transmission without separate explicit authorization.

## Current continuation order

1. Keep the accepted Edge1 public front door and accepted Business159 release-owned deployment model unchanged.
2. Keep `/etc/systemd/system` at the accepted `root:root 0755` trust boundary; do not use the emergency rollback without fresh review.
3. Rerun the hardened Secure MCP tunnel compatibility validator read-only and require `EDGE1_TUNNEL_COMPAT_DOCTOR=PASS`.
4. Capture/classify the five remaining security-inventory records metadata-only and record the exact evidence directory.
5. Rerun the executable Control Surfaces inventory and corrected Asterisk audit.
6. Continue Business159 custom-MCP attachment/read-only/staged-filesystem acceptance when an approved connector runtime is available; do not enable raw shell merely for acceptance.
7. Upload/install the already validated Business159/cross-host Skill packages in a supported Skill runtime when desired; packaging is complete, installation is not.
8. Stop at the attended Edge1 tunnel-activation boundary for explicit approval; do not start or enable the tunnel merely because the compatibility validator passes.
9. Leave DTMF provider work pending until an external response arrives.

## Safety boundary

No credentials or secret values in Git/chat/evidence. No public MCP proxy. No new WAN management listener. Do not modify DNS, firewall, certificates, authentication, production traffic, SIP/carrier routing, emergency behavior, alert delivery, calls/DTMF, or retained evidence merely from this state file. Future privileged modifications to `/etc/systemd/system` remain separately approval-gated; the accepted 2026-08-20 repair does not authorize additional metadata or unit changes. Inspect first; preserve unrelated work; back up before mutations; validate; preserve rollback; stop at explicit credential/account/security/production boundaries.
