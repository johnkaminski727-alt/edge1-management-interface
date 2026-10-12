# Edge2 Agent Shell Claude connector

**Operator-approved full access**, the same design as the Edge1 connector
(`claude-agent-shell-connector.md`): the root Edge2 Agent Shell
(`127.0.0.1:8114`) behind a claude.ai custom connector at
`https://mcp-edge2.ww.cx/mcp`. Anyone who can sign in to it has root on Edge2.

Differences from Edge1:

- **Front end: Caddy.** The installer adds one managed block, between
  `# BEGIN edge2-claude-gateway` and `# END edge2-claude-gateway`, to
  `/etc/caddy/Caddyfile`. It validates the result with `caddy validate`, saves
  `Caddyfile.pre-edge2-claude-<time>`, reloads Caddy, and restores the backup if
  the reload fails. Re-running replaces the block; it never duplicates it.
- **Certificates:** Caddy obtains and renews the certificate itself. There is no certbot step.
- `/mcp` and `/token` use `remote_ip 160.79.104.0/21`. Caddy passes the real client
  address (`header_up X-Forwarded-For {remote_host}`); a forged header is ignored.
- Agent Shell token source: `/etc/edge2-agent-shell/mcp-token`.

## Install

1. DNS: `A` record `mcp-edge2.ww.cx` → the same address as `edge2.ww.cx`.
2. On Edge2, from a fresh checkout:
   `sudo sh deploy/edge2-claude-gateway/install-edge2-claude-gateway.sh` (dry run), then `--apply`.
3. Add the new TOTP secret to an authenticator (account `Edge2 Claude connector`),
   add the connector in claude.ai with the printed client ID **and** secret, and set
   its tools to **Needs approval**.

## Off switches

| Action | Command |
|---|---|
| Instant off | `sudo touch /etc/edge2-claude-gateway/disabled` |
| Full off | `sudo sh deploy/edge2-claude-gateway/install-edge2-claude-gateway.sh --disable` (removes the Caddy block, stops the service) |
| Revoke all Claude sessions | stop the service, delete `/var/lib/edge2-claude-gateway/state.json`, start it |

Logs: `/var/log/edge2-claude-gateway/audit.jsonl` (gateway) and
`/var/log/caddy/mcp-edge2-access.log` (Caddy).
