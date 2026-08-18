# WW.CX Private AI browser interface — activation handoff

Date: 2026-08-18

## Repository completion

The browser-interface implementation is merged in both authoritative repositories.

Edge1 repository:

- repository: `johnkaminski727-alt/edge1-management-interface`
- merged PR: `#353`
- merge commit: `06be73788deafca2b0197797c9ebb71898717841`
- added Edge1 outbound pull worker, hardened systemd unit, unit tests, CI, and deployment/trust-boundary documentation.

WW.CX website repository:

- repository: `johnkaminski727-alt/ww-cx-website`
- merged PR: `#69`
- merge commit: `f8a25f050ad13a81c744249c6107f86f0e848303`
- upgraded the authenticated `/admin/bigbird-ai-chat.php` interface, tool opt-ins, queue scope mapping, safe provenance display, worker result preservation, and browser CI validation.

## Validation completed before merge

Website PR #69:

- PHP syntax: PASS;
- JavaScript syntax: PASS;
- browser security contract: PASS.

Edge1 PR #353:

- `Validate repository`: PASS;
- `Edge1 Operator Validation`: PASS;
- `Validate Private AI browser worker`: PASS;
- worker compile/unit tests: PASS;
- fixed loopback gateway boundary validation: PASS.

Local isolated worker self-test also passed for exact queue and gateway URL enforcement and signing-header generation.

## Intended normal URL

After website deployment and Edge1 worker activation:

`https://ww.cx/admin/bigbird-ai-chat.php`

This route reuses the existing WW.CX administrator session and CSRF infrastructure.

## Architecture

```text
Authenticated browser
  -> https://ww.cx/admin/bigbird-ai-chat.php
  -> same-origin /admin/bigbird-ai-queue.php
  -> private signed queue
  <- Edge1 outbound private-ai-browser-worker.service
  -> http://127.0.0.1:8787/v1/chat
```

The browser never receives gateway HMAC material or worker HMAC material. The accepted Private AI gateway remains loopback-only on `127.0.0.1:8787`.

## Telephony integration

The browser now exposes a read-only Asterisk/FreePBX opt-in through the accepted `telephony:read` gateway capability. It is intended to surface sanitized telephony/PJSIP/PBX health and aggregate call/interconnect context.

No call origination, trunk/endpoint/routing edit, dialplan reload, service restart, AMI/ARI mutation, database query, DTMF transmission, emergency-path action, or credential disclosure was enabled.

## Mail integration direction

Email/correspondence should be part of the same Private AI control plane, but remains a separate permission family.

Existing Edge1 components support a safe staged path:

- inbound mail-hub health/status/audit/quarantine metadata;
- outbound correspondence preparation whose accepted state is `prepared_not_sent`;
- identity-aware sender-selection/compliance controls.

Recommended scopes:

- `mail.status.read` for sanitized operational metadata;
- `mail.correspondence.read` only after a mailbox/content adapter preserves private/shared mailbox boundaries;
- `mail.draft.prepare` for AI-assisted preparation through the existing no-send gateway;
- actual send/delete/archive/unsubscribe/forward/configuration actions only as separately reviewed mutation scopes.

No mail-delivery authority is implied by `chat:general` or any read scope.

## Remaining live activation work

The repository implementation is complete, but the product is **not yet accepted as live** until both host sides are deployed and exercised.

### 1. Edge1

Use an authenticated Edge1 execution path and confirm:

- host is `edge1.ww.cx`;
- repository checkout is on merged main `06be73788deafca2b0197797c9ebb71898717841` or a later main containing it;
- `bigbird-ai-gateway.service` remains active;
- gateway remains on `127.0.0.1:8787` only;
- intended service identity is still `bigbird-ai`;
- no unrelated dirty worktree exists.

Then install/activate only the reviewed worker using `deploy/private-ai-browser-worker.service`, reusing existing server-side signing values through `/etc/wwcx/private-ai-browser-worker.env`. Do not print secret values into evidence.

Verify after activation:

- worker active/enabled;
- no new public listener;
- gateway still loopback-only;
- worker can reach the exact HTTPS WW.CX queue;
- worker can reach the exact loopback gateway;
- logs contain no secret values.

### 2. WW.CX Business159/shared hosting

Use the existing Git-controlled deployer from the authoritative checkout:

```text
~/apps/ww-cx-website/scripts/deploy-business159.sh --dry-run
~/apps/ww-cx-website/scripts/deploy-business159.sh
```

Confirm deployment from `origin/main` containing merge `f8a25f050ad13a81c744249c6107f86f0e848303` or later. Preserve the documented document-root owner/group/mode invariants.

### 3. Browser acceptance

Open:

`https://ww.cx/admin/bigbird-ai-chat.php`

Acceptance requires:

- existing WW.CX login/session is honored;
- one baseline chat request completes through the browser path;
- source/provenance rendering is safe;
- documentation/Communications/telephony opt-ins remain read-only and fail closed;
- no secret appears in browser responses or developer-visible page configuration;
- port 8787 remains private;
- no PBX or mail mutation occurs.

## Current blocker in the 2026-08-18 ChatGPT session

No authenticated Edge1 live-shell connector was available in the active tool environment, no shared-hosting shell/deployer connector was available, and the Opera browser connector was installed but not connected. Therefore live host deployment and authenticated browser acceptance were not executed in that session.

Do not report the browser product as live until the activation steps above are completed with direct host/browser evidence.
