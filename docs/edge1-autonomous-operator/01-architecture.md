# Edge1 Autonomous Operator Architecture

## Purpose

Provide a persistent authenticated operating path from ChatGPT to Edge1 without repeated SSH, passphrase, command-relay, or output-relay work.

## Components

1. A custom MCP app in the authorized ChatGPT workspace.
2. A Secure MCP Tunnel or equivalent approved private transport.
3. An `edge1-operator-mcp` systemd service bound only to localhost or the private tunnel interface.
4. A dedicated `edge1-operator` Unix account with no interactive password.
5. Root-owned, audited wrappers for privileged operations.
6. Structured filesystem, Git, service, package, database, deployment, and evidence tools.
7. An audited bounded shell operation for tasks not covered by structured tools.
8. The `edge1-authenticated-operator` and `wwcx-engineering-agent` skills as the policy and workflow layers.

## Trust boundaries

- ChatGPT never receives private keys, passwords, bearer tokens, recovery codes, or raw connector credentials.
- Authentication material remains in root-readable configuration or an approved secret store on Edge1.
- The service verifies the expected hostname and executing principal before mutation.
- Every modifying request has an execution ID, timestamp, authenticated caller, risk class, sanitized input, result, and validation record.
- The service cannot modify its own authentication material or erase its audit history through ordinary tool calls.

## Connectivity

Preferred path:

```text
ChatGPT workspace
    |
Secure MCP Tunnel
    |
edge1-operator-mcp.service
    |
edge1-operator account
    |
audited sudo wrappers
    |
Edge1 repositories, services, databases, and operating system
```

No new unauthenticated public listener is permitted. The service starts at boot, restarts on failure, exposes health and readiness checks, and reconnects after temporary tunnel interruption.

## Capability model

Structured operations are preferred for predictable validation and audit records. A general bounded shell operation remains available for unforeseen diagnostics and administration.

Initial read-only capabilities:

- identity and preflight;
- system, process, listener, disk, and environment status;
- file and directory reads;
- Git status, diff, log, and remote inspection;
- service status and journal retrieval;
- HTTP and port checks.

Subsequent modifying capabilities:

- staged atomic file writes and rollback;
- branch, commit, push, pull-request, and validated merge workflows;
- service start, stop, restart, and reload with health verification;
- package installation and upgrade with recorded package state;
- named database profiles, backup, query, reversible migration, and restore;
- deployment planning, apply, verify, snapshot, and rollback;
- bounded shell execution with timeout, output limits, cancellation, redaction, and evidence capture.

## Repository placement

The initial implementation belongs in `johnkaminski727-alt/edge1-management-interface` because that repository already contains Edge1 service assets, connector documentation, validation patterns, deployment tooling, records governance, and operational evidence controls. A separate repository should be created later only if the implementation becomes independently releasable or its permission boundary must differ materially.
