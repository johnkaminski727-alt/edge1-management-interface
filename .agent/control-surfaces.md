# Edge1 Control Surfaces — Current State

Last reconciled: 2026-08-18  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Workstream: Control Surfaces / exposure reduction / private operational diagnostics

## Current verified repository state

A read-only Control Surfaces foundation has been prepared for the existing Edge1 Operations API. It adds fixed diagnostic profiles for listener classification, Asterisk, Kamailio and FreePBX status and adds only non-mutating fixed-argv actions to the operations allowlist.

The implementation does not accept arbitrary commands, backend URLs, ports, file paths or Asterisk/Kamailio command text from a caller. Output is bounded and secret-like fields are redacted.

The required classes are:

- `public-infrastructure`;
- `peering`;
- `private-control`;
- `internal-service`;
- `unknown-needs-attribution`.

Classification is intentionally conservative. Unknown/public Asterisk surfaces are not assumed to be peering dependencies without fresh host evidence.

## Browser integration

The companion `ww-cx-website` workstream adds an authenticated `Control Surfaces` page to the existing Operations Center. It reuses the server-side HMAC operations bridge and does not expose Edge1 signing material or direct machine access to the browser.

FreePBX Administration and UCP native-session controls remain closed/disabled until a separately reviewed temporary-session broker exists and is live-validated.

## AI boundary

The design extends the accepted private BigBird pattern: external providers may analyze bounded results through private, allowlisted tools, but provider selection does not grant new tool authority. No direct provider-to-shell, AMI, ARI, database or unrestricted HTTP access is introduced.

## Live execution status

No fresh authenticated Edge1 execution path was available in the 2026-08-18 repository-authoring session. Therefore no present-day listener, Apache, nftables, WireGuard, FreePBX, Asterisk, Kamailio, database, Node, DNS, TLS or external reachability state is claimed from this workstream, and no production change was executed from it.

The next live step is the fresh authenticated inventory required by `docs/control-surfaces/README.md`, followed by evidence-backed exposure reduction with a predeclared rollback for each change.

## Safety boundary

Do not infer a live deployment from repository CI. Do not change carrier routing, originate calls/messages, alter emergency calling, open live carrier peering traffic for testing, rotate credentials, expose secrets, or classify an unknown listener as safe to change without dependency evidence.
