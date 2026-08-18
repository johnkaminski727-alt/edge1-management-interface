# Edge1 Control Surfaces — Activation Handoff

Date: 2026-08-18
Status: repository-prepared; live activation still incomplete

## Prepared repository foundation

The Edge1 repository contains the merged read-only Control Surfaces diagnostics increment built on the existing loopback-only HMAC Operations API. The companion `johnkaminski727-alt/ww-cx-website` `main` contains the authenticated Operations Center Control Surfaces page.

Relevant repository milestones:

- PR #355 — read-only Control Surfaces diagnostics foundation, merge `5a9b071d401ed6eb551b11b8ee1aefde65e3620b`;
- PR #356 — repository-state reconciliation, merge `13e3d658247a076f427ee907526780de0caf4054`;
- PR #357 — browser-baseline reconciliation, merge `918b58ad878704c419ca0b0a406f3ecb87a73f2b`;
- PR #359 — bounded live-inventory runner, merge `efd3ffdbc424678553d39017341dc8f69b6aebc8`;
- `ww-cx-website` PR #71 — Operations Center Control Surfaces page, merge `faf73cc09854653bdba03ceff0c2baed88ea67e1`.

PR #359 added a fixed read-only inventory runner with protected evidence output, sanitization, SHA-256 manifests, static safety tests and dedicated CI. Repository validation does not itself prove current production state.

## Current authenticated execution path

A connected Opera browser was re-inspected on 2026-08-18 and showed an authenticated 1984 Hosting session with an active QEMU out-of-band console for `edge1.ww.cx`.

The Opera connector cannot type into the QEMU canvas. Therefore the available live path is presently a human-relay path: ChatGPT prepares an exact reviewed paste-ready block, the user pastes it into the authenticated console, and the resulting output is returned/inspected for validation.

This is sufficient to perform a controlled live continuation without sharing credentials in chat, but it is not yet the permanent MCP operator connection.

## Current outside-in baseline

Direct browser observations established:

- `https://edge1.ww.cx/` served the Debian Apache default page instead of the intended `https://creekco.ca/time/` redirect;
- `https://edge1.ww.cx/admin/` exposed the FreePBX Administration landing surface over public HTTPS;
- `https://edge1.ww.cx/ucp/` exposed the FreePBX UCP login over public HTTPS;
- rendered FreePBX pages contained runtime/session-adjacent and internal-network information intentionally omitted from durable records;
- a browser request to the known loopback-intended Operations API port `8097` was inconclusive;
- `https://creekco.ca/time/` was reachable;
- `https://ww.cx/admin/bigbird-control-surfaces.php` returned `404 Not Found`, so the merged Control Surfaces page was not deployed at that production URL;
- existing WW.CX Operations Console/admin routes remained behind the established sign-in boundary;
- authenticated WW.CX browser acceptance was not executed because the available browser connector cannot enter credentials.

These observations do not substitute for fresh authenticated host inventory.

## Live continuation sequence

1. Through the authenticated QEMU relay or the completed permanent operator, verify `edge1.ww.cx` and the authenticated principal.
2. Inspect `/opt/edge1-management-interface` branch, HEAD, remotes and dirty state. Preserve any unrelated local work.
3. Run `scripts/control-surfaces-live-inventory.sh` and retain its protected host-local evidence.
4. Review the sanitized evidence and classify each listener exactly as `public-infrastructure`, `peering`, `private-control`, `internal-service`, or `unknown-needs-attribution`.
5. Identify verified SIP/TLS/RTP/media/DNS/certificate and management dependencies before changing listener bindings, nftables or Apache.
6. Create backup/recovery and explicit rollback for the first proposed mutation.
7. Apply the smallest evidence-backed change, validate syntax first, reload/restart only directly affected services, then verify listeners, firewall, authentication, public infrastructure, peering and fresh logs.
8. Remove ordinary WAN reachability to FreePBX Administration/UCP only after the private replacement path plus FreePBX redirects, cookies, WebSockets, CSP and `X-Frame-Options` behavior are understood and accepted.
9. Configure ordinary `edge1.ww.cx` HTTP(S) requests to redirect to `https://creekco.ca/time/` only after current vhost/TLS/service routing proves the redirect safe.
10. Establish the approved Business159 execution path, run the documented WW.CX deployment dry run, preserve the hosting ownership/mode invariants, deploy authoritative `origin/main`, and verify the exact deployed revision.
11. Perform authenticated WW.CX browser acceptance for Operations Center and Control Surfaces behavior.
12. Complete and attach the permanent private Edge1 Operator/MCP transport so future ChatGPT sessions can use bounded authenticated tools without relying on the QEMU relay.
13. Record before/after evidence, rollback, exact repository/deployed revisions and remaining blockers.

## Permanent operator state

The repository already contains Edge1 Operator / MCP scaffolding, runtime/tool registry assets, installer/service assets and the loopback Operations API. Historical documentation records an earlier `edge1-operator-mcp.service` installation, but the current permanent-operator effort still requires fresh host validation, production MCP transport completion and private ChatGPT workspace/tunnel attachment.

Do not treat historical service status as current proof of connector usability.

## Archive-ready checkpoint

The sanitized archive-readiness reconciliation is:

`docs/archive/edge1-control-surfaces-operator-archive-readiness-20260818.md`

Use that record together with `.agent/control-surfaces.md`, current Git history and a fresh host inspection when resuming this work.

## Safety boundary

Do not paste credentials or secret values into chat. Do not infer live host state from CI. Do not change carrier routing, originate production calls/messages for testing, alter emergency calling, rotate credentials, expose a new public management listener, or modify an unknown listener before its owner, purpose, dependencies and rollback are sufficiently understood.
