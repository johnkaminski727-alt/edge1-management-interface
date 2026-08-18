# Edge1 Control Surfaces / Permanent Operator Archive Readiness

Date: 2026-08-18
Classification: sanitized engineering handoff and archive-readiness record
Systems: `edge1.ww.cx`, WW.CX Operations Center, Edge1 Operator / MCP

## Purpose

This record preserves the verified repository and outside-in state reached while preparing the Edge1 Control Surfaces and permanent ChatGPT operator path for live completion. It is intentionally an **archive-readiness** record, not a declaration that the permanent MCP connector or the Control Surfaces production rollout is complete.

The record exists to prevent future work from losing the distinction between:

- repository implementation that is merged and validated;
- historical records that claim prior host installation;
- outside-in browser observations made on 2026-08-18;
- the currently available authenticated 1984 Hosting QEMU console session;
- production state that still requires fresh authenticated host evidence.

## Authoritative repository baseline

At the time this archive-readiness record was created, authoritative `main` for `johnkaminski727-alt/edge1-management-interface` was:

```text
75539c9c97e29a25127aef21b58166bdaf3a97a9
```

That head includes unrelated work after the Control Surfaces increment. The Control Surfaces / operator evidence below therefore cites the specific relevant merges rather than implying that every later `main` commit belongs to this workstream.

Relevant completed repository milestones include:

- Control Surfaces read-only diagnostics foundation: PR #355, merge `5a9b071d401ed6eb551b11b8ee1aefde65e3620b`.
- Repository-state reconciliation: PR #356, merge `13e3d658247a076f427ee907526780de0caf4054`.
- Outside-in browser-baseline reconciliation: PR #357, merge `918b58ad878704c419ca0b0a406f3ecb87a73f2b`.
- Bounded live inventory runner: PR #359, merge `efd3ffdbc424678553d39017341dc8f69b6aebc8`.
- Companion WW.CX Control Surfaces page: `johnkaminski727-alt/ww-cx-website` PR #71, merge `faf73cc09854653bdba03ceff0c2baed88ea67e1`.

PR #359 added:

- `scripts/control-surfaces-live-inventory.sh`;
- `docs/control-surfaces/live-inventory.md`;
- `tests/test_control_surfaces_live_inventory.py`;
- `.github/workflows/control-surfaces-live-inventory.yml`.

Its applicable repository, operator, Control Surfaces and dedicated live-inventory validations passed on the exact PR head before merge.

## Current repository-side architecture

The accepted architecture remains:

```text
ChatGPT / authorized MCP client
        |
private authenticated transport
        |
Edge1 Operator / bounded tool boundary
        |
loopback Edge1 Operations API and/or fixed reviewed handlers
        |
Edge1 services and repositories
```

The existing Operations API is designed as a loopback-only HMAC-authenticated, replay-protected, server-side allowlisted execution boundary. Control Surfaces diagnostic actions are fixed and non-mutating by default. The intended permanent MCP layer must not weaken those controls.

No archive record should be interpreted as authorization for arbitrary command strings, arbitrary URLs, arbitrary ports, unrestricted filesystem access, unrestricted SQL, raw AMI/ARI, or provider-selected machine authority.

## Authenticated 1984 Hosting / QEMU access finding

During this session, the connected Opera browser was re-inspected and showed that the 1984 Hosting account session is authenticated. The Edge1 VPS remote-access page displayed an active out-of-band QEMU connection for `edge1.ww.cx`.

The browser connector can read and navigate the provider page but does not expose keyboard input into the QEMU canvas. Therefore the session provides a valid **human-relay execution path** but not direct autonomous command execution from ChatGPT.

Approved continuation model:

```text
ChatGPT prepares exact reviewed command block
        |
user pastes block into authenticated QEMU console
        |
output is returned or inspected
        |
ChatGPT validates and prepares next bounded step
```

This model must not be described as direct connector execution.

## Outside-in production baseline preserved

The 2026-08-18 browser baseline established:

- ordinary `https://edge1.ww.cx/` presented the Debian Apache default page rather than the intended CreekCo redirect;
- FreePBX Administration under `/admin/` was WAN-reachable over ordinary public HTTPS;
- FreePBX UCP under `/ucp/` was WAN-reachable over ordinary public HTTPS;
- the FreePBX pages exposed runtime/session-adjacent and internal-network information that is intentionally omitted from repository records;
- `https://creekco.ca/time/` was reachable;
- the WW.CX Control Surfaces production URL returned `404 Not Found`;
- the existing WW.CX Operations Console/admin routes remained behind the established sign-in boundary;
- a browser request to the loopback-intended Operations API port `8097` was inconclusive and must not be treated as evidence of open or closed WAN exposure.

These observations are outside-in evidence only and are not substitutes for fresh host-side listener, firewall, Apache, FreePBX, Asterisk, Kamailio, DNS, TLS, service or dependency evidence.

## Live inventory package now available

`main` contains the fixed read-only inventory runner documented in `docs/control-surfaces/live-inventory.md`.

The runner creates a private timestamped evidence directory, applies `umask 077`, retains sanitized output plus command status/timestamps, and writes SHA-256 manifests. It is designed to inventory identity, repositories, listeners, routes, Apache, nftables, WireGuard, Asterisk, Kamailio, FreePBX, local HTTP behavior, the Operations API, BigBird health and TLS identity without intentionally mutating production state.

The retained host evidence directory is not a Git artifact and must not be committed wholesale.

## Historical deployment-record reconciliation

`docs/edge1-operator/deployment-completion-record.md` is a historical record that states `edge1-operator-mcp.service` was installed, enabled and active after earlier validation.

Newer operator status documents, however, still list production MCP transport completion, protocol/runtime integration, current host validation and workspace/tunnel attachment as incomplete. The current session has not independently executed shell commands on Edge1 to verify the historical service claim.

Archive interpretation:

- preserve the deployment completion record as historical evidence;
- do not delete or rewrite its historical assertions;
- do not treat it as current proof that the permanent ChatGPT MCP connection is usable now;
- require fresh host inspection before relying on the service status, bind address, runtime implementation or transport attachment.

## Permanent operator work still open

The permanent operator is not considered complete until direct evidence confirms all applicable items below:

1. production MCP transport is implemented and reviewed;
2. protocol handlers expose only the intended bounded tools;
3. runtime actions delegate through the reviewed Operations API and/or equally constrained handlers;
4. the Edge1 host installation is freshly inspected and validated;
5. the operator service identity, startup persistence, listener and logs are verified;
6. the transport remains private and does not create a new public management listener;
7. ChatGPT can discover the connector and successfully invoke identity/health plus approved diagnostics;
8. audit/evidence generation works and secret handling is validated;
9. arbitrary shell/URL/port/path/SQL/AMI/ARI capability is not introduced;
10. rollback and recovery are documented and tested sufficiently for the deployed architecture.

## Control Surfaces production work still open

After the permanent execution path is available, the remaining live sequence is:

1. verify host and authenticated principal;
2. inspect repository branch/head/dirty state and preserve unrelated work;
3. run the bounded read-only live inventory;
4. classify every relevant listener as `public-infrastructure`, `peering`, `private-control`, `internal-service`, or `unknown-needs-attribution`;
5. identify verified SIP/TLS/RTP/media/DNS/certificate and management dependencies;
6. define backup and rollback before each material mutation;
7. remove unintended WAN FreePBX Administration/UCP exposure only after the private replacement path and dependent behavior are proven;
8. configure ordinary `edge1.ww.cx` web behavior to redirect to `https://creekco.ca/time/` only after vhost/TLS/service routing is understood;
9. deploy the merged WW.CX Control Surfaces page through the approved Business159 deployment path;
10. perform authenticated browser acceptance;
11. complete the temporary/private FreePBX session mechanism;
12. reconcile repository documentation with the final observed live state.

## Archive package index

Retain these files together as the minimum durable repository package for this workstream:

1. `.agent/control-surfaces.md`
2. `docs/handoff/edge1-control-surfaces-activation-handoff-20260818.md`
3. `docs/control-surfaces/README.md`
4. `docs/control-surfaces/live-inventory.md`
5. `scripts/control-surfaces-live-inventory.sh`
6. `tests/test_control_surfaces_live_inventory.py`
7. `.github/workflows/control-surfaces-live-inventory.yml`
8. `docs/edge1-operator/08-mcp-integration-status.md`
9. `docs/edge1-operator/13-completion-status.md`
10. `docs/edge1-operator/deployment-completion-record.md`
11. `server/edge1_operations_api.py`
12. `config/edge1-operations-allowlist.json`
13. `deploy/edge1-operations-api.service`
14. existing `server/edge1_operator_*` implementation files and `deploy/edge1-operator/` assets
15. this archive-readiness record.

Use current Git history and pull requests as the authoritative content/version source rather than copying these files into a second uncontrolled repository tree.

## Archive boundary

This record is sanitized and suitable for durable repository retention. It intentionally excludes:

- passwords, private keys, HMAC material, cookies, provider session data, recovery codes and tunnel credentials;
- raw FreePBX session-adjacent values or internal-network values observed in browser-rendered pages;
- raw host logs, database dumps, call/message/customer records, or carrier credentials;
- unredacted future live-inventory evidence;
- claims that historical service state is current without fresh verification.

Host-local evidence should be retained only under the approved protected evidence procedure, with sanitization and hashes, and imported into durable archives only when specifically reviewed as safe.

## Restore / continuation order

For a future operator or ChatGPT session, recover context in this order:

1. this archive-readiness record;
2. `.agent/control-surfaces.md`;
3. `docs/handoff/edge1-control-surfaces-activation-handoff-20260818.md`;
4. `docs/control-surfaces/live-inventory.md`;
5. `docs/edge1-operator/08-mcp-integration-status.md` and `13-completion-status.md`;
6. current GitHub `main`, relevant PR history and CI;
7. a fresh authenticated host inspection before making any claim about present production state.

## Archive readiness result

Repository documentation is ready to be retained as a sanitized project checkpoint once the accompanying reconciliation changes are merged. The workstream itself remains **active / incomplete** until the permanent authenticated MCP tool and the remaining live Control Surfaces acceptance criteria are directly verified.
