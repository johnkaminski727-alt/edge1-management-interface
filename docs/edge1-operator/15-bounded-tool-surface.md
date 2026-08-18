# Edge1 Operator bounded tool surface

Date: 2026-08-18
Classification: repository-confirmed design and source-validation record

## Objective

Replace the legacy generic MCP execution concept with a narrow, named, read-only tool surface that reuses the hardened loopback Edge1 Operations API.

## Security properties

- MCP callers cannot supply shell commands, executable names, URLs, ports, paths, service names, SQL, AMI/ARI commands, or Operations API action names.
- All MCP tool schemas reject additional properties.
- The operator Operations API client refuses non-loopback URLs.
- Runtime mappings contain only fixed read-only action names.
- Mutating Operations API actions remain present only for separately authorized workflows and are not exposed through this MCP contract.
- HMAC signing material is read locally from the existing protected secret file and is never returned by the client.
- Operations API replay protection and audit logging remain authoritative for delegated action calls.
- Adapter exceptions are reduced to a generic `runtime_error` rather than exposing internal exception strings.

## Tool-to-action mapping

`edge1.inventory` composes the fixed Control Surfaces summary, service list, interface/routes, disk state, repository state/head, and BigBird health into one read-only structured result.

Other named tools delegate only the fixed action groups defined in `server/edge1_operator_runtime.py`.

## Validation performed before publication

Local focused validation against the proposed source files:

```text
python3 -m py_compile server/*.py
python3 -m pytest -q tests/test_edge1_operator_bounded_tools.py tests/test_edge1_operator_integration_flow.py
11 passed
```

This validates source behavior only. Repository CI and live Edge1 validation remain separate acceptance gates.

## Remaining boundary

This change intentionally does not invent a public transport or claim permanent ChatGPT connectivity. The next source/runtime milestone is the approved private production MCP transport and its installation/acceptance path, followed by fresh Edge1 verification.
