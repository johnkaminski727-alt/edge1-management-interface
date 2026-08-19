# Edge1 Secure MCP Tunnel activation

Last reconciled: 2026-08-18
Status: live non-secret staging accepted; account/credential enrollment and Edge1 Operator tunnel acceptance pending

## Objective

Attach the already-verified private Edge1 Operator MCP service to ChatGPT without exposing Edge1 management ports to the public internet and without weakening the Operator's existing bearer authentication.

The local service remains:

- `edge1-operator-mcp.service`
- user/group `edge1-operator`
- Streamable HTTP endpoint `http://127.0.0.1:8102/mcp`
- bearer token source `/etc/edge1-operator/mcp-token`
- no generic `edge1.exec`; only the reviewed named parameterless tool contract

## Live tunnel-client compatibility discovery

Fresh production inspection on 2026-08-18 found an existing root-owned `/usr/local/bin/tunnel-client` already carrying the active `bigbird-ai-tunnel.service` runtime.

Verified identity:

- version `0.0.10+105e17a79a36e4e5c897fd698ed2b8dbf935b144`;
- upstream source commit `105e17a79a36e4e5c897fd698ed2b8dbf935b144` exists in `openai/tunnel-client`;
- live binary SHA-256 `937347720ef32ef3ef2f68f4496b2dd7917ca5e575452ed87a4ce78d0262a100`;
- root-owned executable at `/usr/local/bin/tunnel-client`;
- active Big Bird tunnel process uses `tunnel-client run --profile bigbird-edge1`;
- Big Bird tunnel health listener is loopback `127.0.0.1:8080`.

The exact upstream 0.0.10 source documents support for `mcp.extra_headers`, `mcp.discovery_extra_headers`, and `env:` / `file:` secret references. Those are the features required by the Edge1 Operator transport.

Do **not** replace or upgrade `/usr/local/bin/tunnel-client` merely to stage the Edge1 Operator tunnel while the Big Bird tunnel is active. The Edge1 Operator assets deliberately reuse this compatible binary and isolate their own runtime files and dynamic loopback health listener.

The installer requires tunnel-client 0.0.10 or later and verifies the `run` and `doctor` command surfaces before staging. It does not install or replace the shared binary.

## Transport design

Use OpenAI Secure MCP Tunnel as an outbound-only transport.

Repository assets under `deploy/edge1-tunnel/` deliberately do not contain a tunnel ID, OpenAI runtime API key, Edge1 MCP bearer value, or other secret.

`tunnel-client.yaml` points the main MCP channel only at `127.0.0.1:8102/mcp`. Both MCP runtime requests and discovery/probe requests send `Authorization` from the environment reference `EDGE1_MCP_AUTHORIZATION`.

The launcher runs as `edge1-operator`, reads the already-existing `/etc/edge1-operator/mcp-token`, constructs `Bearer <token>` only in its process environment, then execs tunnel-client. It does not create a second persistent copy of the Edge1 MCP token.

The OpenAI runtime API key is expected at `/etc/edge1-tunnel/runtime-api-key` and is consumed by tunnel-client through a `file:` reference. The tunnel ID is expected as the raw ID in `/etc/edge1-tunnel/tunnel-id` and is exported by the launcher as `CONTROL_PLANE_TUNNEL_ID`.

Runtime namespace is intentionally separate from Big Bird:

- Edge1 Operator tunnel health: dynamic `127.0.0.1:0` with URL written under `/run/edge1-secure-mcp-tunnel/`;
- Edge1 Operator tunnel PID: `/run/edge1-secure-mcp-tunnel/tunnel-client.pid`;
- Edge1 Operator tunnel config: `/etc/edge1-tunnel/tunnel-client.yaml`;
- Big Bird's existing profile/service is not modified or restarted.

## Repository staging

The installer is intentionally two-phase. It never creates credentials and never enables or starts the tunnel service.

Preconditions:

1. A compatible official `tunnel-client` version 0.0.10 or later exists at `/usr/local/bin/tunnel-client`.
2. `edge1-operator` and `edge1-operator-mcp.service` already exist.
3. The local Operator remains healthy on loopback `8102`.
4. Any existing tunnel-client consumer, including Big Bird, remains untouched.

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
- shared `/usr/local/bin/tunnel-client` is unchanged;
- Big Bird's tunnel service remains active and unchanged;
- no tunnel ID or API key is generated;
- no public listener, firewall rule, DNS record, Apache proxy, MCP auth change, or Operator restart is performed.

## Accepted live non-secret staging

Live staging completed on 2026-08-18 from reviewed repository revision `c1390fc973c7afd3fabebff922bb10b1a0213a51`.

Accepted production evidence:

- evidence bundle: `/var/lib/wwcx-deployment-evidence/secure-mcp-tunnel-stage/20260818T195627Z`;
- rollback: `/var/lib/wwcx-deployment-evidence/secure-mcp-tunnel-stage/20260818T195627Z/rollback.sh`;
- shared tunnel-client remained version `0.0.10+105e17a79a36e4e5c897fd698ed2b8dbf935b144` and SHA-256 `937347720ef32ef3ef2f68f4496b2dd7917ca5e575452ed87a4ce78d0262a100`;
- `bigbird-ai-tunnel.service` remained active with MainPID `449` before and after staging and kept loopback listener `127.0.0.1:8080`;
- `edge1-operator-mcp.service` remained active on `127.0.0.1:8102`, and an unauthenticated request still returned HTTP `401`;
- `/etc/edge1-tunnel/tunnel-client.yaml`, `/usr/local/libexec/edge1-tunnel/edge1-secure-mcp-tunnel.sh`, and `/etc/systemd/system/edge1-secure-mcp-tunnel.service` were staged with the intended ownership/modes;
- `edge1-secure-mcp-tunnel.service` remained disabled and inactive;
- `/etc/edge1-tunnel/tunnel-id` and `/etc/edge1-tunnel/runtime-api-key` remained absent;
- no second tunnel-client process was started;
- the primary checkout remained untouched at its pre-existing commit.

This establishes the end of the non-secret host-side staging phase. The next phase begins only after authorized OpenAI workspace/account enrollment supplies a tunnel ID and runtime API key locally on Edge1.

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

Verify there is still no public Edge1 MCP listener, the original Operator remains loopback-only on `127.0.0.1:8102`, and `bigbird-ai-tunnel.service` remains healthy.

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

Removing the Edge1 Operator tunnel transport must not remove, replace, restart, or reconfigure the shared tunnel-client binary or `bigbird-ai-tunnel.service`, and must not require any change to `edge1-operator-mcp.service`, its local token, the Operations API, firewall, DNS, SSH, Apache, SIP, SNMP, or other Edge1 services.

## Completion condition

The permanent Operator is complete only when all of the following agree:

- Edge1 Operator tunnel service is healthy and outbound-only;
- existing Big Bird tunnel remains healthy;
- local MCP remains bearer-protected and loopback-only;
- ChatGPT can discover exactly the reviewed bounded tools through the selected tunnel;
- `edge1.identity` and `edge1.health` succeed from ChatGPT;
- approved read-only diagnostics succeed with durable audit evidence;
- tunnel stop/disable and account-side revocation paths are documented and tested;
- no secret values are recorded in repository or evidence artifacts.
