# Edge1 Control Surfaces — Activation Handoff

Date: 2026-08-18

## Prepared repository foundation

The Edge1 repository contains a deploy-ready read-only diagnostics increment built on the existing loopback-only HMAC Operations API. The companion WW.CX website `main` contains the first-class authenticated Operations Center page.

Repository validation covers fixed profiles, secret redaction, required surface classes, no shell invocation, non-mutating allowlist entries, PHP syntax, fixed browser-side action selection and closed native-session controls.

Repository-state reconciliation PR #356 was merged as `13e3d658247a076f427ee907526780de0caf4054` after its applicable GitHub Actions validations passed.

## Current outside-in baseline

A connected browser produced these direct observations during the authorized activation session:

- `https://edge1.ww.cx/` serves the Debian Apache2 default page. The intended ordinary public redirect to `https://creekco.ca/time/` is not active yet.
- A navigation request to `http://edge1.ww.cx/` ended at the same HTTPS Apache default page. The connector cannot distinguish a browser HTTPS upgrade from a server-side HTTP redirect, so the exact HTTP redirect chain remains unverified.
- `https://creekco.ca/time/` loads successfully and is presently browser-reachable.
- `https://ww.cx/admin/bigbird-control-surfaces.php` returns `404 Not Found`, so the merged Control Surfaces page is not present at the production WW.CX URL yet.
- `https://ww.cx/admin/` reaches the existing WW.CX Store sign-in page. The connected browser does not hold an authenticated WW.CX admin session and cannot enter credentials, so authenticated browser acceptance has not been executed.

These observations establish a production baseline only. They do not substitute for authenticated listener, firewall, vhost, telephony, database or service dependency inspection on Edge1.

## What has not been executed

No live Edge1 host mutation, service restart, Apache change, firewall change, listener bind change, FreePBX proxy, public redirect, native control session, provider credential change or shared-hosting deployment has been executed from the current session because an authenticated Edge1 shell/operator connector and Business159 deployment execution path are not exposed to it.

Outside-in browser checks have now been executed as described above, but authenticated WW.CX browser acceptance remains blocked by the lack of an authenticated controllable browser session.

## Exact live continuation sequence

1. Establish the approved authenticated Edge1 execution path and verify host/principal before mutation.
2. Capture a timestamped protected evidence directory and fresh listener/service/Apache/nftables/WireGuard/telephony/database/Node/DNS/TLS/Operations/AI inventory.
3. Preserve the outside-in baseline above and repeat it after each public-facing change.
4. Attribute every discovered listener to one of the five Control Surfaces classes; leave unknown surfaces unchanged.
5. Identify verified SIP signaling/TLS/media/DNS/certificate dependencies before any binding or firewall change.
6. Back up each affected configuration and write the rollback command before applying it.
7. Apply the smallest evidence-backed exposure-reduction change, validate syntax first, reload/restart only affected services, then verify listeners, firewall, auth, public infrastructure, peering and fresh logs.
8. Configure ordinary `edge1.ww.cx` HTTP(S) behavior to redirect to `https://creekco.ca/time/` only after current vhost/certificate/service-specific routing proves the redirect is safe.
9. Establish the approved Business159 execution path, run the documented WW.CX deployment dry run, preserve the document-root `wwcxjywl:nobody` / `0750` invariant, deploy `origin/main`, and verify the exact deployed revision.
10. Perform authenticated WW.CX browser acceptance for the Operations Center and Control Surfaces page, including authorization denial, diagnostics, stale/error rendering and secret-boundary checks.
11. Design/activate a temporary same-origin FreePBX session broker only after current FreePBX routing, cookies, WebSockets, CSP, `X-Frame-Options` and path behavior are inspected; prove it never opens the backend to WAN.
12. Keep AI integrations private, provider-independent and tool-allowlisted; no provider receives uncontrolled machine access.
13. Record before/after evidence, rollback, exact repository/deployed revisions and remaining blockers.

## Smallest operator actions when continuation is blocked

Expose/connect the approved authenticated Edge1 Live Shell or equivalent restricted operator connector to this ChatGPT session. Do not paste credentials or secret values into chat.

Separately expose/connect the approved Business159/shared-hosting deployment execution path capable of running the repository deployer. Do not paste hosting credentials, private keys, deploy keys, tokens or cookies into chat.
