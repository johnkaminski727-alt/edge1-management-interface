# Edge1 Mail Gateway — Local Preflight State

Date: 2026-08-22
Status: repository preparation only; no live Postfix changes

## Parent work

- PR #507 / `65782108b25baf466b19eb505b4c130752f30225`: disabled Edge1 Mail Gateway v1 architecture.
- PR #508 / `125bdb481b105215a99275ea78cddaa8bf7f12eb`: local SMTP -> Mail Room `production_native` intake path and safe Postfix rendering.

## This phase

Adds a read-only authenticated-operator preflight that:

- captures current Postfix configuration and listener evidence;
- copies `main.cf`/`master.cf` into the evidence package for comparison only;
- renders the proposed loopback-only gateway fragments;
- detects existing virtual-domain/transport collisions;
- fails if live TCP/25 is non-loopback;
- fails if generated state includes `ww.cx` or is not loopback-only;
- never edits Postfix or changes DNS/listeners.

## Boundary after merge

The next live step is to run the preflight from an authenticated Edge1 operator session after reconciling `/opt/edge1-management-interface` to current `main`.

Do not apply local Postfix configuration until the resulting evidence has been reviewed. Public SMTP, DNS/MX, firewall, certificate, provider cancellation, and outbound mail remain separate explicit authorization boundaries.
