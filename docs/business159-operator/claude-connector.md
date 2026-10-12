# Business159 Claude connector (stage 1)

Publishes the bounded `business159-live-shell` operator to a claude.ai custom
connector. It is a separate route from the ChatGPT Secure MCP Tunnel, which is
unchanged.

```text
claude.ai ──https──▶ mcp-b159.ww.cx (Edge1 nginx, TLS)
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
  in nginx and again in the gateway. nginx overwrites any client-supplied
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
(`business159-operator`, `/etc/business159-operator`, the libexec wrapper, and
`business159-live-shell` under `/opt/edge1-management-interface`).

The installer runs from any checkout that contains this change, such as a fresh
clone in the operator's home directory. It copies the gateway to
`/opt/business159-claude-gateway/` and never updates the shared
`/opt/edge1-management-interface` checkout, which may be on a working branch.

1. DNS: add an `A` record `mcp-b159.ww.cx` pointing to the same address as `edge1.ww.cx`.
2. Fresh checkout: `git clone --depth 1 https://github.com/johnkaminski727-alt/edge1-management-interface ~/b159-claude-gateway && cd ~/b159-claude-gateway`
3. Dry run: `sudo sh deploy/business159-claude-gateway/install-business159-claude-gateway.sh`
4. Apply: `sudo sh deploy/business159-claude-gateway/install-business159-claude-gateway.sh --apply`
   - Generates the client ID, client secret and TOTP secret, and prints them **once**.
   - Starts the service, then adds the nginx site in two steps: an HTTP-only
     site for the ACME challenge (`certbot --webroot`, existing ACME account,
     renewals reload nginx), then the full HTTPS site. Each step runs
     `nginx -t` and rolls back on failure. The site binds to the same address as
     `edge1.ww.cx`; existing sites and the default server are untouched.
   - Runs postflight checks, including that `edge1.ww.cx` still answers.
5. In an authenticator (e.g. Yubico Authenticator → Add account), enter the TOTP
   secret or scan the QR code (shown when `qrencode` is installed).
6. claude.ai → Customize → Connectors → Add custom connector:
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
also delete `/etc/nginx/sites-available/mcp-b159.ww.cx.conf`, `/var/www/b159-claude-acme`,
`/etc/systemd/system/business159-claude-gateway.service`,
`/opt/business159-claude-gateway` and `/etc/business159-claude-gateway`, then `systemctl daemon-reload`. The ChatGPT
tunnel and the Business159 runtime are not modified by install or rollback.

## Full access (operator-approved)

On 2026-10-12 the operator chose full access for this connector, so Claude can
deploy, fix drift and reconcile the server with Git without an SSH session in
between. It is opt-in and reversible:

```sh
sudo sh deploy/business159-claude-gateway/install-business159-claude-gateway.sh --apply --full-access
sudo sh deploy/business159-claude-gateway/install-business159-claude-gateway.sh --apply --read-only   # back to stage 1
```

`--full-access` writes `/etc/systemd/system/business159-claude-gateway.service.d/20-access.conf`
(`B159_GATEWAY_ACCESS=full`). The gateway then lists every tool, including
`business159_exec`, `business159_fs_*` and deploy apply, and starts each child
with all three `BUSINESS159_*` mutation gates set to `1`. Everything else is
unchanged: TOTP sign-in, Anthropic-only `/mcp` and `/token`, the audit log, and
the off switches below. Keep the connector's tools on **Needs approval**.

Anyone who can sign in to this connector can change anything the `wwcxjywl`
account can, including `public_html`, mail and the store's private config.

## Validation

```sh
python3 tests/test_business159_claude_gateway.py
sh -n deploy/business159-claude-gateway/install-business159-claude-gateway.sh
```
