# Edge1 Secure MCP Tunnel activation

Last reconciled: 2026-08-18
Status: repository staging prepared; account/credential enrollment and live tunnel acceptance pending

## Objective

Attach the already-verified private Edge1 Operator MCP service to ChatGPT without exposing Edge1 management ports to the public internet and without weakening the Operator's existing bearer authentication.

The local service remains:

- `edge1-operator-mcp.service`
- user/group `edge1-operator`
- Streamable HTTP endpoint `http://127.0.0.1:8102/mcp`
- bearer token source `/etc/edge1-operator/mcp-token`
- no generic `edge1.exec`; only the reviewed named parameterless tool contract

## Transport design

Use OpenAI Secure MCP Tunnel as an outbound-only transport.

Repository assets under `deploy/edge1-tunnel/` deliberately do not contain a tunnel ID, OpenAI runtime API key, Edge1 MCP bearer value, or other secret.

`tunnel-client.yaml` points the main MCP channel only at `127.0.0.1:8102/mcp`. Both MCP runtime requests and discovery/probe requests send `Authorization` from the environment reference `EDGE1_MCP_AUTHORIZATION`.

The launcher runs as `edge1-operator`, reads the already-existing `/etc/edge1-operator/mcp-token`, constructs `Bearer <token>` only in its process environment, then execs tunnel-client. It does not create a second persistent copy of the Edge1 MCP token.

The OpenAI runtime API key is expected at `/etc/edge1-tunnel/runtime-api-key` and is consumed by tunnel-client through a `file:` reference. The tunnel ID is expected as the raw ID in `/etc/edge1-tunnel/tunnel-id` and is exported by the launcher as `CONTROL_PLANE_TUNNEL_ID`.

## Repository staging

The installer is intentionally two-phase. It never creates credentials and never enables or starts the tunnel service.

Preconditions:

1. The official `tunnel-client` binary is installed at `/usr/local/bin/tunnel-client`.
2. `edge1-operator` and `edge1-operator-mcp.service` already exist.
3. The local Operator remains healthy on loopback `8102`.

Dry run and staging:

```sh
sudo sh deploy/edge1-tunnel/install-edge1-secure-mcp-tunnel.sh
sudo sh deploy/edge1-tunnel/install-edge1-secure-mcp-tunnel.sh --apply
```

Expected post-stage state:

- `/etc/edge1-tunnel/tunnel-client.yaml` is root-owned and readable by `edge1-operator`;
- `/usr/local/libexec/edge1-tunnel/edge1-secure-mcp-tunnel.sh` is root-owned executable code;
- `/etc/systemd/system/edge1-secure-mcp-tunnel.service` is installed;
- service is disabled and inactive;
- no tunnel ID or API key is generated;
- no public listener, firewall rule, DNS record, Apache proxy, MCP auth change, or Operator restart is performed.

## Human credential/account gate

Do not paste any credential into Git, chat, issue comments, PRs, command history shared as evidence, or screenshots.

The authorized workspace/account operator must complete these steps locally:

1. Create or select a Secure MCP Tunnel associated with the intended ChatGPT workspace and obtain its `tunnel_...` ID.
2. Create a tunnel runtime API key with the required tunnel Read/Use permissions.
3. On Edge1, write the raw tunnel ID to `/etc/edge1-tunnel/tunnel-id`.
4. On Edge1, write the raw runtime API key to `/etc/edge1-tunnel/runtime-api-key`.
5. Set both files to `root:edge1-operator` mode `0640`.

This is the explicit credential boundary. Repository automation does not perform it.

## Doctor and activation

After local credential provisioning, validate without exposing secret values:

```sh
sudo -u edge1-operator /usr/local/libexec/edge1-tunnel/edge1-secure-mcp-tunnel.sh doctor
```

The doctor command must succeed before service activation.

Then start attended, without enabling persistence yet:

```sh
sudo systemctl start edge1-secure-mcp-tunnel.service
sudo systemctl --no-pager --full status edge1-secure-mcp-tunnel.service
```

Read the dynamically selected loopback health URL without assuming a port:

```sh
sudo cat /run/edge1-secure-mcp-tunnel/health-url
```

Verify there is still no public Edge1 MCP listener and that the original Operator remains loopback-only on `127.0.0.1:8102`.

Only after doctor, tunnel readiness, ChatGPT discovery, identity/health calls, evidence, and rollback checks pass should persistence be enabled:

```sh
sudo systemctl enable edge1-secure-mcp-tunnel.service
```

## ChatGPT-side acceptance

In the authorized ChatGPT workspace/account:

1. Enable the applicable developer/custom-app capability.
2. Create a custom MCP app using Tunnel as the connection.
3. Select the tunnel associated with the Edge1 runtime.
4. Scan tools.
5. Confirm the discovered contract is exactly the expected named parameterless Edge1 tools; no generic execution tool may appear.
6. Call `edge1.identity` and confirm Edge1 reports the expected host/principal/service identity.
7. Call `edge1.health` and confirm the Operations API is loopback, healthy, and mutations remain disabled.
8. Call one or more approved read-only diagnostics and confirm durable Edge1 audit evidence.

Do not publish the app workspace-wide until this private acceptance passes.

## Failure and rollback

Before persistence is enabled, rollback is simply:

```sh
sudo systemctl stop edge1-secure-mcp-tunnel.service
```

For a persistent installation:

```sh
sudo systemctl disable --now edge1-secure-mcp-tunnel.service
```

Tunnel revocation/deletion and runtime API-key revocation are account actions and must be performed by the authorized human operator through the OpenAI account/workspace boundary.

Removing the tunnel transport must not require any change to `edge1-operator-mcp.service`, its local token, the Operations API, firewall, DNS, SSH, Apache, SIP, SNMP, or other Edge1 services.

## Completion condition

The permanent Operator is complete only when all of the following agree:

- Edge1 tunnel service is healthy and outbound-only;
- local MCP remains bearer-protected and loopback-only;
- ChatGPT can discover exactly the reviewed bounded tools through the selected tunnel;
- `edge1.identity` and `edge1.health` succeed from ChatGPT;
- approved read-only diagnostics succeed with durable audit evidence;
- tunnel stop/disable and account-side revocation paths are documented and tested;
- no secret values are recorded in repository or evidence artifacts.
