# Business159 Persistent Secure MCP Tunnel

## Purpose

Run the bounded `business159-live-shell` MCP continuously on Edge1 through the dedicated OpenAI Secure MCP Tunnel named `Business159 Operator`, without sharing the Edge1 Operator or Big Bird tunnel runtime/secret namespace and without adding a public listener.

Architecture:

`ChatGPT -> Business159 Operator tunnel -> Edge1 tunnel-client -> stdio business159-live-shell -> strict SSH -> Business159`

The tunnel client uses the official stdio MCP binding. The local MCP remains an account-level shared-host operator and retains `BatchMode=yes`, strict host-key verification, expected-host verification, expected-principal verification, bounded output/time, and redaction.

## Isolation

Dedicated local identity: `business159-operator`.

Dedicated paths:

- `/etc/business159-tunnel/` — tunnel profile, tunnel id and runtime API key;
- `/etc/business159-operator/` — root-controlled reviewed SSH config and known-hosts database;
- `/var/lib/business159-operator/` — non-secret service state/home;
- `/run/business159-secure-mcp-tunnel/` — PID and health URL;
- `/usr/local/libexec/business159-tunnel/` — root-owned launch wrappers;
- `business159-secure-mcp-tunnel.service` — dedicated systemd unit.

The service identity must not be a member of Edge1 Operator, Big Bird, telephony, web-server, or other unrelated privileged groups. The Business159 runtime API key and tunnel id are separate from Edge1 tunnel material.

## Lifecycle

1. Run `install-business159-secure-mcp-tunnel.sh` with no argument. This is a true dry run and must not create files/users, start services, or enable boot persistence.
2. Install source-controlled assets with `--apply`. This stages files only and leaves the service disabled/inactive.
3. Provision four local-only items without putting values in Git/chat/evidence: `/etc/business159-tunnel/tunnel-id`, `/etc/business159-tunnel/runtime-api-key`, `/etc/business159-operator/ssh_config`, and `/etc/business159-operator/known_hosts`. All four files must be owner `root:business159-operator`, mode `0640`.
4. Run `validate-business159-secure-mcp-tunnel.sh`. It verifies systemd syntax, strict noninteractive SSH identity, and `tunnel-client doctor`/stdio MCP readiness. Do not start or enable the service if this fails.
5. Start attended with `systemctl start business159-secure-mcp-tunnel.service`.
6. Read the generated health base URL from `/run/business159-secure-mcp-tunnel/health-url` and require `/readyz` success.
7. In ChatGPT create/select app `Business159 Authenticated Operator`, connection `Tunnel`, tunnel `Business159 Operator`, then discover tools and call `business159_connection_test`, `business159.identity`, `business159.git_state`, `business159.deployment_status`, `business159.php_status`, and `business159.web_status`.
8. Only after ChatGPT acceptance succeeds, run `systemctl enable business159-secure-mcp-tunnel.service`.
9. Run `verify-business159-secure-mcp-tunnel.sh`.
10. Perform a controlled `systemctl restart business159-secure-mcp-tunnel.service`, rerun `/readyz`, and repeat `business159_connection_test` from ChatGPT. No terminal-started tunnel process is permitted as the accepted state.

## Rollback

Before host installation, record the repository commit, sibling tunnel active/enabled states, and hashes/modes of any colliding destination files. The staging installer refuses to overwrite an already active/enabled Business159 service. If first activation fails, stop the Business159 unit, leave it disabled, restore the recorded destination files (or remove only files created by this installation), run `systemctl daemon-reload`, and verify Edge1 Operator/Big Bird services remain at their preserved states.

Do not change DNS, certificates, firewall rules, SSH authentication policy, Edge1/Big Bird tunnel units, or public listeners as part of this procedure.
