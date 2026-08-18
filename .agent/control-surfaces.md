# Edge1 Control Surfaces — Current State

Last reconciled: 2026-08-18  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Workstream: Control Surfaces / exposure reduction / permanent private operator

## Relevant repository milestones

The read-only Control Surfaces diagnostics foundation is merged through PR #355:

```text
5a9b071d401ed6eb551b11b8ee1aefde65e3620b
```

The companion authenticated WW.CX Operations Center interface is merged to `johnkaminski727-alt/ww-cx-website` through PR #71:

```text
faf73cc09854653bdba03ceff0c2baed88ea67e1
```

Repository-state reconciliation was merged through PR #356:

```text
13e3d658247a076f427ee907526780de0caf4054
```

Outside-in browser-baseline reconciliation was merged through PR #357:

```text
918b58ad878704c419ca0b0a406f3ecb87a73f2b
```

The bounded read-only live-inventory package was merged through PR #359:

```text
efd3ffdbc424678553d39017341dc8f69b6aebc8
```

PR #359 added `scripts/control-surfaces-live-inventory.sh`, its documentation, static safety-contract tests and dedicated CI. The applicable repository, Edge1 Operator, Control Surfaces and dedicated live-inventory validations passed on the exact PR head before merge.

Authoritative repository `main` has subsequently advanced with unrelated work. Use current Git history as the source of truth rather than treating the Control Surfaces merge SHA as the repository head.

## Current verified repository state

The Edge1 foundation provides fixed diagnostic profiles for listener classification, Asterisk, Kamailio and FreePBX status and only non-mutating fixed-argv Control Surfaces actions in the Operations API allowlist.

The accepted implementation does not accept arbitrary commands, backend URLs, ports, file paths or Asterisk/Kamailio command text from a caller. Output is bounded and secret-like fields are redacted.

The required listener classes are exactly:

- `public-infrastructure`;
- `peering`;
- `private-control`;
- `internal-service`;
- `unknown-needs-attribution`.

Classification is intentionally conservative. Unknown/public listeners are not assumed safe or legitimate without fresh host dependency evidence.

## Permanent operator / MCP state

The repository already contains substantial Edge1 Operator / MCP scaffolding and deployment assets, plus the loopback HMAC Operations API used by the Control Surfaces bridge.

The permanent target remains:

```text
ChatGPT / authorized MCP client
        |
private authenticated transport
        |
Edge1 Operator bounded tool boundary
        |
loopback Operations API and/or fixed reviewed handlers
        |
Edge1 services and repositories
```

The production MCP transport, current host validation and private ChatGPT workspace/tunnel attachment are not yet directly verified complete. Historical documents that record an earlier `edge1-operator-mcp.service` installation are retained as historical evidence but are not treated as current proof.

See:

- `docs/edge1-operator/08-mcp-integration-status.md`;
- `docs/edge1-operator/13-completion-status.md`;
- `docs/archive/edge1-control-surfaces-operator-archive-readiness-20260818.md`.

## Authenticated 1984 Hosting / QEMU access

The connected Opera browser was re-inspected on 2026-08-18 and showed an authenticated 1984 Hosting account session with an active QEMU out-of-band console for `edge1.ww.cx`.

The Opera connector can inspect and navigate the provider page but cannot type into the QEMU canvas. Therefore the current authenticated host path is a **human-relay execution path**:

```text
ChatGPT prepares exact bounded paste-ready commands
        |
user pastes them into the authenticated QEMU console
        |
output is returned or inspected
        |
ChatGPT validates and prepares the next bounded step
```

Do not describe this as direct autonomous shell execution.

## Browser / outside-in baseline — 2026-08-18

Direct connected-browser observations established:

- `https://edge1.ww.cx/` presented the Debian Apache default page; the intended ordinary public redirect to `https://creekco.ca/time/` was not active.
- `https://edge1.ww.cx/admin/` resolved to the FreePBX Administration surface. The native administration surface was therefore WAN-reachable over ordinary public HTTPS and is treated as `private-control` pending live dependency inspection and exposure reduction.
- `https://edge1.ww.cx/ucp/` exposed the FreePBX User Control Panel login over public HTTPS and is likewise treated as `private-control`.
- Rendered FreePBX pages contained runtime/session-adjacent and internal-network values; those values are intentionally excluded from durable documentation.
- A browser request to the known loopback-intended Operations API port `8097` did not finish loading. That result is inconclusive and is not evidence that the port is either open or closed from WAN.
- `https://creekco.ca/time/` loaded successfully.
- `https://ww.cx/admin/bigbird-control-surfaces.php` returned `404 Not Found`, so the merged Control Surfaces page was not present at the production WW.CX URL during the observation.
- the existing Operations Console and admin routes redirected an unauthenticated browser to the established WW.CX sign-in boundary.
- the available browser control could not enter WW.CX credentials, so authenticated browser acceptance remained unexecuted.

These are outside-in observations only. They do not replace fresh host-side listener, firewall, vhost, telephony, DNS, TLS or service dependency evidence.

## Live inventory readiness

`main` now contains `scripts/control-surfaces-live-inventory.sh`, documented in `docs/control-surfaces/live-inventory.md`.

The runner is read-only by design and creates a private timestamped evidence directory with sanitized retained output, command status/timestamps and SHA-256 hashes. It covers host identity, repositories, listeners, routes, Apache, nftables, WireGuard, Asterisk, Kamailio, FreePBX, local HTTP behavior, the Operations API, BigBird health and TLS identity where the authenticated principal is permitted to inspect them.

The evidence directory is host-local protected operational evidence and must not be committed wholesale to Git.

## Remaining live sequence

1. Verify host and authenticated principal through the QEMU relay or the completed permanent operator.
2. Inspect `/opt/edge1-management-interface` branch/head/dirty state and preserve unrelated work.
3. Run the bounded read-only live inventory and review sanitized evidence.
4. Attribute all listeners to the five required classes and leave unresolved listeners unchanged until understood.
5. Identify verified SIP/TLS/RTP/media/DNS/certificate and management dependencies before firewall/listener/vhost changes.
6. Create backup/recovery and explicit rollback before each material mutation.
7. Remove unintended WAN FreePBX Administration/UCP exposure only after the private replacement path and dependent path/cookie/WebSocket/security behavior are proven.
8. Configure ordinary `edge1.ww.cx` behavior to redirect to `https://creekco.ca/time/` only after current vhost/TLS/service routing proves that change safe.
9. Establish the approved Business159 execution path, dry-run and deploy the authoritative WW.CX `main`, preserving hosting ownership/mode invariants.
10. Perform authenticated WW.CX browser acceptance.
11. Complete and validate the permanent private MCP/operator connection and temporary/private FreePBX session mechanism.
12. Reconcile final repository documentation with directly observed production state.

## Archive readiness

The sanitized checkpoint is prepared in:

`docs/archive/edge1-control-surfaces-operator-archive-readiness-20260818.md`

That record is suitable for durable repository retention but intentionally marks the workstream **active / incomplete** until the permanent MCP tool and remaining live Control Surfaces acceptance criteria are directly verified.

## Safety boundary

Do not infer current live host state from repository CI or historical completion records. Do not change carrier routing, originate calls/messages, alter emergency calling, rotate credentials, expose secrets, create a new public management listener, or classify an unknown listener as safe to change without dependency evidence and a rollback path.
