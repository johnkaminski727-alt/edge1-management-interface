# AVA MCP Connector Architecture

## Current production model

AVA's conversational gateway uses authenticated MCP-backed reads for current Edge1 operational state. The model never receives MCP bearer tokens or broker credentials.

Path:

`AVA browser/controller -> Big Bird AI Gateway -> AVA Operator Broker -> Edge1 Operator MCP -> Operations API`

The AVA Operator Broker listens only on loopback (`127.0.0.1:8118`) and owns the protected MCP credential. The gateway runs as `bigbird-ai` and receives access only to the broker token through the `bigbird-ai` group.

## Model-facing MCP tools

The normal AVA conversational tool catalog exposes only:

- `edge1_mcp_read` — bounded current Edge1 identity, health, inventory, service, network, disk, Big Bird, Operations API, repository and approved configuration state.
- `business159_mcp_read` — bounded Business159 operational reads through the broker. The Business159 backend remains the existing authenticated hosting-principal path until its secure tunnel exposes a local callable MCP client endpoint.

The older model-facing names (`edge1_operator_read`, `business159_operator_read`) remain accepted only as internal compatibility aliases and are not advertised to AVA.

## Mutation boundary

Direct model mutation and shell tools are not part of AVA's conversational MCP catalog.

Older concepts such as `edge1_service_repair`, `edge1_unrestricted_shell`, and `business159_unrestricted_shell` have been superseded for normal AVA operation by the AVA Executive Dispatcher and its registered bounded workflows. The helper library retains compatibility aliases for rollback/tests, but the live gateway always requests read-only MCP tool definitions.

Backend work therefore follows:

`AVA Executive -> capability registry -> bounded workflow/action broker -> worker/bot -> report back to AVA`

This keeps conversational retrieval separate from backend mutation authority.

## Scope mapping

- Existing trusted `edge1:status:read` requests expose only `edge1_mcp_read`.
- Trusted internal `operator:read` requests expose `edge1_mcp_read` and `business159_mcp_read`.
- External/non-internal requests receive no MCP tools.
- `operator:actions:routine` and `operator:shell:escape` do not add conversational tools; backend actions are handled by AVA Executive.

## Retired integrations

`ava-operations-reader` is retired and no longer exposed to AVA. Its profile, manifest and implementation remain only for historical audit, rollback and regression tests. The manifest is explicitly marked `status=retired`, `exposed_to_ava=false`, and `superseded_by=ava-mcp-operator-broker`.

The old `tools/install_ava_operator_gateway_integration.py` and `tools/install_ava_admin_functions_gateway_integration.py` patch-on-live installers targeted the obsolete 0.3.x gateway series. They are retained only as fail-closed retirement stubs and exit without modifying the gateway.

## Broker service dependencies

`wwcx-ava-operator-broker.service` requires the normal `edge1-operator-mcp.service`. Agent Shell and the Business159 secure tunnel are optional/wanted escalation transports and no longer prevent Edge1 MCP reads if either optional service is unavailable.

The Admin Functions synchronizer is not automatically enabled by MCP broker installation. `deploy/ava-operator-broker/install.sh --apply` installs only the broker. The separate synchronizer requires explicit `--with-admin-sync`.

## Verification

Primary regression suite:

```text
python3 -m unittest \
  tests.test_ava_operator_gateway_tools \
  tests.test_ava_operator_broker \
  tests.test_ava_operator_policy \
  tests.test_ava_readonly_gateway \
  tests.test_ava_operations_reader -q
```

Live signed acceptance:

```text
sudo python3 tools/ava_gateway_signed_acceptance.py --mcp
```

The live acceptance must demonstrate unsigned rejection, normal Library/model success, nonce replay rejection, an `edge1_mcp_read` model tool call, and no active MCP shell hosts.
