# Edge1 Operator MCP Integration Status

Last reconciled: 2026-08-18
Status: repository foundation present; permanent ChatGPT MCP attachment not yet directly verified

## Completed repository foundation

- Repository architecture
- Operator service scaffold
- Runtime boundary and runtime-bridge scaffolding
- Tool-contract and registry scaffolding
- Bootstrap procedure
- Installation verification assets
- Initial validation coverage
- Loopback Edge1 Operations API with HMAC authentication, replay protection and server-side action allowlist
- Fixed read-only Control Surfaces diagnostic actions
- Bounded Control Surfaces live-inventory runner and dedicated CI

The intended architecture remains:

```text
ChatGPT / authorized MCP client
        |
private authenticated transport
        |
edge1-operator-mcp service
        |
bounded operator policy / tool layer
        |
loopback Edge1 Operations API and/or reviewed fixed handlers
        |
Edge1 services and repositories
```

## Current access-path finding

On 2026-08-18, the connected Opera browser was re-inspected and showed an authenticated 1984 Hosting session with an active QEMU out-of-band console for `edge1.ww.cx`.

The browser connector can inspect and navigate the provider page but does not expose keyboard input into the QEMU canvas. This creates a valid human-relay execution path for reviewed paste-ready command blocks, but it is not direct ChatGPT shell execution and it is not the permanent MCP connection.

## Remaining integration work

1. Complete and review the production MCP transport.
2. Connect MCP protocol handlers to the bounded runtime / Operations API without introducing arbitrary shell, URL, port, path, SQL, AMI or ARI authority.
3. Complete installer/service hardening needed by the production transport.
4. Run the full repository validation suite on the exact implementation revision.
5. Perform a fresh Edge1 host installation/service/listener/log validation.
6. Attach the approved private ChatGPT workspace/tunnel transport.
7. Prove ChatGPT discovery plus successful identity/health and approved diagnostic calls.
8. Prove audit/evidence behavior and rollback before declaring the permanent operator complete.

## Historical installation note

`docs/edge1-operator/deployment-completion-record.md` preserves an earlier record that states `edge1-operator-mcp.service` was installed, enabled and active. That record is retained as historical evidence, but the current session has not independently re-run shell validation on Edge1.

Therefore the historical record must not be used by itself as current proof that the production MCP transport, present service implementation, listener state or ChatGPT attachment is complete.

## Security boundary

Private credentials, HMAC material, provider session data and tunnel secrets remain outside Git. They must be provisioned through the trusted deployment/connection environment and never copied into repository documentation or chat.

The permanent MCP layer must preserve the existing fixed/allowlisted execution model and must not create a public management listener merely to make ChatGPT connectivity easier.

## Completion condition

The project is complete only when the operator is freshly validated on Edge1, discoverable by the authorized ChatGPT MCP client through the approved private transport, able to execute the intended bounded tools with durable audit evidence, and recoverable through a documented rollback path.

See `docs/archive/edge1-control-surfaces-operator-archive-readiness-20260818.md` for the sanitized archive-readiness reconciliation.
