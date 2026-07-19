# Edge1 Operator Tool Registry Integration

## Purpose

Define the mapping between MCP-facing operations and the internal Edge1 runtime capabilities.

## Registry model

The MCP adapter exposes a controlled registry rather than directly exposing implementation internals.

Each tool definition includes:

- tool name;
- purpose;
- input contract;
- authorization class;
- runtime handler;
- validation requirements;
- audit requirements.

## Initial tool groups

### Read-only

- identity
- health
- preflight
- filesystem inspection
- repository inspection
- service inspection
- log inspection

### Controlled mutation

- staged file changes;
- validated service operations;
- repository operations;
- deployment workflows;
- recovery workflows.

## Safety requirements

All mutating operations must:

1. validate the target environment;
2. create an execution identifier;
3. record audit metadata;
4. preserve recovery information;
5. execute validation after completion.

## Status

Registry integration is being completed as part of Edge1 Operator v0.1.
