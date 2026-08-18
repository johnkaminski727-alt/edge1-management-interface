# Edge1 Control Surfaces — Current State

Last reconciled: 2026-08-18  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Workstream: Control Surfaces / exposure reduction / private operational diagnostics

## Repository completion

The read-only Control Surfaces foundation is merged to authoritative Edge1 `main` through PR #355:

```text
merge: 5a9b071d401ed6eb551b11b8ee1aefde65e3620b
```

The companion authenticated WW.CX Operations Center interface is merged to `johnkaminski727-alt/ww-cx-website` `main` through PR #71:

```text
merge: faf73cc09854653bdba03ceff0c2baed88ea67e1
```

The repository-state reconciliation was merged through PR #356:

```text
merge: 13e3d658247a076f427ee907526780de0caf4054
```

Before the Edge1 feature merge, all four applicable GitHub Actions runs passed on the exact PR head:

- Validate repository;
- Edge1 Operator Validation;
- Edge1 operations API;
- Validate Edge1 Control Surfaces.

The website PR passed its Control Surfaces interface and WW.CX AI browser validation workflows before merge.

## Current verified repository state

The Edge1 foundation adds fixed diagnostic profiles for listener classification, Asterisk, Kamailio and FreePBX status and only non-mutating fixed-argv actions to the operations allowlist.

The implementation does not accept arbitrary commands, backend URLs, ports, file paths or Asterisk/Kamailio command text from a caller. Output is bounded and secret-like fields are redacted.

The required classes are:

- `public-infrastructure`;
- `peering`;
- `private-control`;
- `internal-service`;
- `unknown-needs-attribution`.

Classification is intentionally conservative. Unknown/public Asterisk surfaces are not assumed to be peering dependencies without fresh host evidence.

## Browser integration

The companion `ww-cx-website` main contains the authenticated `Control Surfaces` Operations Center page and canonical navigation entry. It reuses the server-side HMAC operations bridge and does not expose Edge1 signing material or direct machine access to the browser.

FreePBX Administration and UCP native-session controls remain closed/disabled until a separately reviewed temporary-session broker exists and is live-validated.

Repository merge does not prove the website files have been deployed to Business159/shared hosting.

## AI boundary

The design extends the accepted private BigBird pattern: external providers may analyze bounded results through private, allowlisted tools, but provider selection does not grant new tool authority. No direct provider-to-shell, AMI, ARI, database or unrestricted HTTP access is introduced.

## Outside-in browser baseline — 2026-08-18

A connected browser produced direct outside-in observations during the authorized activation session:

- `https://edge1.ww.cx/` loaded the Debian Apache2 default page (`Apache2 Debian Default Page: It works`). The intended ordinary public redirect to `https://creekco.ca/time/` is therefore not active yet.
- Navigating to `http://edge1.ww.cx/` ended at the same HTTPS Apache default page. The browser connector does not expose enough transport detail to distinguish browser HTTPS upgrade from a server-side HTTP redirect, so no claim is made about the exact HTTP status/redirect chain.
- `https://creekco.ca/time/` loaded successfully with title `CreekCo | WW.CX Time Service`, confirming the approved redirect destination is presently browser-reachable.
- `https://ww.cx/admin/bigbird-control-surfaces.php` returned `404 Not Found`. The merged Control Surfaces page is therefore not present at that production URL yet.
- `https://ww.cx/admin/` redirected to the existing `WW.CX Store sign in` page, confirming the existing production admin surface is reachable but the connected browser does not hold an authenticated WW.CX admin session.
- The available browser control does not support entering credentials or completing the WW.CX sign-in form, so authenticated Control Surfaces acceptance remains unexecuted.

These browser observations are baseline evidence only. They do not replace the required fresh authenticated Edge1 listener/service/firewall/vhost inventory.

## Live execution status

No fresh authenticated Edge1 shell/operator execution path is available in the current session. Therefore no present-day listener, Apache configuration, nftables, WireGuard, FreePBX, Asterisk, Kamailio, database, Node, DNS, TLS, service dependency or privileged runtime state is claimed from shell evidence, and no production Edge1 mutation has been executed.

The live browser baseline above proves that the ordinary public Edge1 redirect and WW.CX Control Surfaces production deployment are still pending. It does not establish why they are pending or whether any service-specific routes have dependencies that constrain the change.

The next live step is the fresh authenticated inventory required by `docs/control-surfaces/README.md`, followed by evidence-backed exposure reduction with a predeclared rollback for each change. The Business159 deployment and authenticated browser acceptance also remain pending an approved execution path.

## Smallest blocked operator action

Expose/connect the approved authenticated Edge1 Live Shell or equivalent restricted operator connector to the active ChatGPT session. Do not paste credentials or secret values into chat.

For the companion WW.CX deployment, expose/connect the approved Business159/shared-hosting deployment execution path capable of running the repository deployer. Do not paste hosting credentials or deploy keys into chat.

## Safety boundary

Do not infer live host state from repository CI. Do not change carrier routing, originate calls/messages, alter emergency calling, open live carrier peering traffic for testing, rotate credentials, expose secrets, or classify an unknown listener as safe to change without dependency evidence.
