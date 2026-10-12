# Edge1 Agent Shell Claude connector

**Operator-approved full access.** This connector puts the root Edge1 Agent
Shell (`127.0.0.1:8114`: shell, file and systemd tools) behind a claude.ai
custom connector at `https://mcp-edge1.ww.cx/mcp`. The operator chose this
explicitly (2026-10-12) after reviewing the read-only and guarded-write
alternatives. Anyone who can sign in to it has root on Edge1.

```text
claude.ai ──https──▶ mcp-edge1.ww.cx (Edge1 nginx, TLS; /mcp + /token: 160.79.104.0/21 only)
                        ▼
              edge1-claude-gateway (127.0.0.1:8151, user edge1-claude-gw, no capabilities)
                        │  OAuth 2.1 + PKCE, single operator, TOTP sign-in, 7-day refresh
                        ▼  adds the Agent Shell bearer token on Edge1
              edge1-agent-shell (127.0.0.1:8114, root)
```

It uses the same gateway as the Business159 connector
(`server/business159_claude_gateway.py`) in HTTP upstream mode, with every tool
allowed (`B159_GATEWAY_TOOLS=*`).

## Safeguards

- Sign-in needs a fresh TOTP code (replay protection; five wrong codes lock it
  for 15 minutes). One pre-registered client; no dynamic registration.
- Refresh tokens expire after **7 days**; access tokens after 1 hour.
- `/mcp` and `/token` only accept Anthropic's outbound range, checked in nginx
  and in the gateway. The gateway and Agent Shell listen on loopback only.
- The gateway runs unprivileged; only the Agent Shell runs as root.
- Audit: `/var/log/edge1-claude-gateway/audit.jsonl` (tool names and argument
  names, never values). The Agent Shell keeps its own ledger at
  `/var/log/wwcx-edge1-agent-shell/audit.jsonl`.
- **Keep the connector's tools on "Needs approval" in claude.ai**, so every
  command needs a click from the operator.
- If the Agent Shell token changes, the gateway returns 502 (not 401). Re-run
  the installer to copy the new token.

## Install

1. DNS: `A` record `mcp-edge1.ww.cx` → the same address as `edge1.ww.cx`.
2. From a fresh checkout: `sudo sh deploy/edge1-claude-gateway/install-edge1-claude-gateway.sh` (dry run), then `--apply`.
3. Add the TOTP secret to an authenticator; add the connector in claude.ai with
   the printed client ID **and** secret; set its tools to **Needs approval**.
4. While on the VPN, signing in needs the `wwcx:vpn-public-https` UFW rule
   (`deploy/edge1-vpn-public-access/`).

## Off switches

| Action | Command |
|---|---|
| Instant off | `sudo touch /etc/edge1-claude-gateway/disabled` |
| Full off | `sudo sh deploy/edge1-claude-gateway/install-edge1-claude-gateway.sh --disable` |
| Revoke all Claude sessions | stop the service, delete `/var/lib/edge1-claude-gateway/state.json`, start it |
| New client secret / TOTP | `--apply --rotate-client-secret` / `--apply --rotate-totp` |

Complete removal: `--disable`, then delete `/etc/nginx/sites-available/mcp-edge1.ww.cx.conf`,
`/etc/systemd/system/edge1-claude-gateway.service`, `/opt/edge1-claude-gateway`,
`/etc/edge1-claude-gateway` and `/var/www/edge1-claude-acme`, and run `systemctl daemon-reload`.
