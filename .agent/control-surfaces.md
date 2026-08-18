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

Before the Edge1 merge, all four applicable GitHub Actions runs passed on the exact PR head:

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

The companion `ww-cx-website` main now contains the authenticated `Control Surfaces` Operations Center page and canonical navigation entry. It reuses the server-side HMAC operations bridge and does not expose Edge1 signing material or direct machine access to the browser.

FreePBX Administration and UCP native-session controls remain closed/disabled until a separately reviewed temporary-session broker exists and is live-validated.

Repository merge does not prove the website files have been deployed to Business159/shared hosting.

## AI boundary

The design extends the accepted private BigBird pattern: external providers may analyze bounded results through private, allowlisted tools, but provider selection does not grant new tool authority. No direct provider-to-shell, AMI, ARI, database or unrestricted HTTP access is introduced.

## Live execution status

No fresh authenticated Edge1 execution path was available in the 2026-08-18 repository-authoring session. Therefore no present-day listener, Apache, nftables, WireGuard, FreePBX, Asterisk, Kamailio, database, Node, DNS, TLS or external reachability state is claimed from this workstream, and no production Edge1 change was executed from it.

The independent web tooling available in the authoring session also did not yield a valid outside-in endpoint result, so no external reachability conclusion is recorded.

The next live step is the fresh authenticated inventory required by `docs/control-surfaces/README.md`, followed by evidence-backed exposure reduction with a predeclared rollback for each change. The shared-hosting deployment and authenticated browser acceptance also remain pending an approved execution path.

## Smallest blocked operator action

Expose/connect the approved authenticated Edge1 Live Shell or equivalent restricted operator connector to the active ChatGPT session. Do not paste credentials or secret values into chat. The Business159/shared-hosting deployer can then be connected/executed separately for the merged website revision.

## Safety boundary

Do not infer a live deployment from repository CI. Do not change carrier routing, originate calls/messages, alter emergency calling, open live carrier peering traffic for testing, rotate credentials, expose secrets, or classify an unknown listener as safe to change without dependency evidence.
