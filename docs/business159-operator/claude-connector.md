# Business159 Claude connector (stage 1)

Publishes the bounded `business159-live-shell` operator to a claude.ai custom
connector. It is a separate route from the ChatGPT Secure MCP Tunnel, which is
unchanged.

```text
claude.ai ──https──▶ mcp-b159.ww.cx (Edge1 Apache, TLS)
                        │  /mcp and /token: Anthropic outbound range only
                        ▼
              business159-claude-gateway (127.0.0.1:8150, business159-operator)
                        │  OAuth 2.1 + PKCE, single operator, TOTP sign-in
                        │  tool allowlist, deploy forced to dry-run, audit log
                        ▼  one stdio child per MCP session
              business159-live-shell.sh ──ssh──▶ Business159 (wwcxjywl)
```

## Boundaries

- **The Edge1 Agent Shell (root, `127.0.0.1:8114`) is never contacted.** Each MCP
  session starts its own bounded `business159-live-shell` child through the same
  wrapper the ChatGPT tunnel uses.
- **Stage 1 tools:** the read-only `business159.*` tools, `business159_connection_test`,
  `business159_inspect`, `business159_fs_status`, `business159_fs_diff`, and
  `business159_deploy` limited to `dryRun=true`. Mail mutations, staged filesystem
  writes and `business159_exec` are neither listed nor callable.
- The child's `BUSINESS159_ALLOW_DEPLOY`, `BUSINESS159_ALLOW_FILESYSTEM` and
  `BUSINESS159_ENABLE_RAW_SHELL` are pinned to `0`, whatever the runtime policy says.
- **Network:** `/mcp` and `/token` accept only `160.79.104.0/21`
  ([Anthropic outbound IPs](https://platform.claude.com/docs/en/api/ip-addresses)),
  in Apache and again in the gateway. Apache drops any client-supplied
  `X-Forwarded-For`. All other paths are 404. The gateway listens on loopback only.
- **Sign-in:** `/authorize` needs a fresh 6-digit TOTP code. Codes cannot be reused,
  and five wrong codes lock sign-in for 15 minutes. There is no dynamic client
  registration: one client ID/secret is entered in claude.ai's Advanced settings,
  and redirects go only to the claude.ai / claude.com callback.
- **Tokens:** access tokens last 1 hour; refresh tokens last 30 days and rotate on
  every use. Only SHA-256 digests are stored (`/var/lib/business159-claude-gateway/state.json`).
- **Audit:** `/var/log/business159-claude-gateway/audit.jsonl` records sign-ins,
  token grants and every tool call or block. It stores tool names and argument
  *names* only, never values or output.

## Install

Prerequisites: the Business159 Secure MCP Tunnel assets are installed
(`business159-operator`, `/etc/business159-operator`, the libexec wrapper), and
`/opt/edge1-management-interface` is at a commit containing this change.

1. DNS: add an `A` record `mcp-b159.ww.cx` pointing to the same address as `edge1.ww.cx`.
2. Dry run: `sudo sh deploy/business159-claude-gateway/install-business159-claude-gateway.sh`
3. Apply: `sudo sh deploy/business159-claude-gateway/install-business159-claude-gateway.sh --apply`
   - Generates the client ID, client secret and TOTP secret, and prints them **once**.
   - Starts the service, issues the certificate (`certbot --apache`, existing ACME
     account), enables the Apache site and runs postflight checks.
4. In an authenticator (e.g. Yubico Authenticator → Add account), enter the TOTP
   secret or scan the QR code (shown when `qrencode` is installed).
5. claude.ai → Customize → Connectors → Add custom connector:
   URL `https://mcp-b159.ww.cx/mcp`; Advanced settings → client ID and secret.
   Connect, then enter the authenticator code on the sign-in page.

## Operate

| Task | Command |
|---|---|
| Status | `systemctl status business159-claude-gateway` · `curl -s 127.0.0.1:8150/healthz` |
| Recent activity | `sudo tail -n 50 /var/log/business159-claude-gateway/audit.jsonl` |
| Emergency off (instant) | `sudo touch /etc/business159-claude-gateway/disabled` |
| Fully disable | `sudo sh .../install-business159-claude-gateway.sh --disable` |
| Revoke all Claude sessions | `sudo systemctl stop business159-claude-gateway && sudo rm /var/lib/business159-claude-gateway/state.json && sudo systemctl start business159-claude-gateway` |
| New client secret | `--apply --rotate-client-secret` (update claude.ai Advanced settings) |
| New TOTP secret | `--apply --rotate-totp` (re-enrol the authenticator) |

## Rollback

`--disable` removes the public site and stops the service. To remove it completely,
also delete `/etc/apache2/sites-available/mcp-b159.ww.cx.conf`,
`/etc/systemd/system/business159-claude-gateway.service` and
`/etc/business159-claude-gateway`, then `systemctl daemon-reload`. The ChatGPT
tunnel and the Business159 runtime are not modified by install or rollback.

## Later stages (not enabled)

Stage 2 (deploy apply with an exact commit) and stage 3 (staged `public_html`
writes) need a deliberate change to `STAGE1_TOOLS` / `DRY_RUN_ONLY_TOOLS`, and the
runtime policy validator, plus review. Raw shell stays off this route.

## Validation

```sh
python3 tests/test_business159_claude_gateway.py
sh -n deploy/business159-claude-gateway/install-business159-claude-gateway.sh
```
