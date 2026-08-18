# Edge1 Autonomous Operator Architecture

## Purpose

Provide a persistent authenticated operating path from ChatGPT to Edge1 without repeated SSH, passphrase, command-relay, or output-relay work.

## Components

1. A custom MCP app in the authorized ChatGPT workspace.
2. A Secure MCP Tunnel or equivalent approved private transport.
3. An `edge1-operator-mcp` systemd service bound only to loopback.
4. A dedicated `edge1-operator` Unix account with no interactive password.
5. The hardened loopback Edge1 Operations API as the fixed-action authority boundary.
6. Named, typed, parameter-constrained operator tools for diagnostics and reviewed operations.
7. Structured snapshot, drift, acceptance, continuation, safe-change, and evidence tooling.
8. The `edge1-authenticated-operator` and `wwcx-engineering-agent` skills as policy and workflow layers.

## Trust boundaries

- ChatGPT never receives private keys, passwords, bearer tokens, recovery codes, or raw connector credentials.
- Authentication material remains in root/operator-readable configuration or an approved secret store on Edge1.
- The MCP HTTP endpoint is loopback-only; a supported private tunnel is the intended remote attachment path.
- Requests carrying an `Origin` header are rejected unless the exact Origin is allowlisted.
- The MCP bearer token is loaded from a local protected file and is never stored in the repository.
- The service verifies its own local health before serving operator calls.
- Every executable operation remains a fixed server-side action behind the Operations API's authentication, replay protection, timeout, mutation classification, and audit controls.
- The service cannot modify its own authentication material or erase its audit history through ordinary tool calls.
- There is **no generic `edge1.exec`, arbitrary shell, caller-controlled argv, caller-controlled service name, caller-controlled path, or caller-controlled URL** in the MCP surface.

## Connectivity

Preferred path:

```text
ChatGPT workspace
    |
Secure MCP Tunnel
    |
127.0.0.1:8102/mcp
    |
edge1-operator-mcp.service
    |
typed MCP adapter/runtime
    |
127.0.0.1:8097 Edge1 Operations API
    |
fixed allowlisted actions + audit trail
```

No new unauthenticated public listener is permitted. The MCP endpoint must remain on loopback. Tunnel provisioning must not change that bind address.

Port `8098` is reserved by the existing WW.CX Portal API Bridge. The Edge1 MCP transport uses dedicated loopback port `8102`; deployment validation must keep those listener assignments distinct.

## MCP transport contract

The repository-side transport uses MCP Streamable HTTP semantics on a single `/mcp` endpoint and intentionally implements a minimal subset needed for the current read-only tool surface:

- JSON-RPC 2.0;
- `initialize`;
- `notifications/initialized`;
- `ping`;
- `tools/list`;
- `tools/call`;
- JSON responses only; GET returns `405 Method Not Allowed` because server-initiated SSE is not required by the current operator;
- one MiB request-body ceiling;
- bearer authentication for every request;
- exact Origin allowlisting when an Origin header is present;
- fixed loopback bind on `127.0.0.1:8102`.

The transport does not provision, configure, authenticate, or publish the Secure MCP Tunnel itself. That is a separate private attachment step and must be completed using the then-current supported OpenAI mechanism without exposing the Edge1 listener publicly.

## Capability model

Structured operations are mandatory. New capabilities must be added as named reviewed tools and mapped to fixed Operations API actions; generic command execution is prohibited.

Initial read-only capabilities include:

- identity and health;
- deterministic host snapshot;
- system/service state;
- network and listener state;
- disk state;
- repository status/head;
- BigBird status;
- Apache, Asterisk, telephony, messaging, and time-authority status;
- selected configuration digests.

Subsequent modifying capabilities, when separately reviewed and authorized, may include:

- a named verified BigBird deployment operation;
- a named reviewed operator deployment operation;
- approved configuration refresh operations;
- explicitly allowlisted service restart operations with precheck/verify/recovery evidence.

Each modifying capability must use the Safe Change Runner lifecycle and a fixed server-side operation definition. Firewall, DNS, SSH, accounts, credentials, keys, certificates, and unrelated networking remain outside this generic framework unless separately authorized and designed.

## Repository placement

The implementation belongs in `johnkaminski727-alt/edge1-management-interface` because that repository already contains Edge1 service assets, connector documentation, validation patterns, deployment tooling, records governance, and operational evidence controls. A separate repository should be created later only if the implementation becomes independently releasable or its permission boundary must differ materially.
