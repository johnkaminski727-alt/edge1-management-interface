# Ava attended unrestricted shell gates

Ava has two independent emergency/diagnostic escape hatches. They are **disabled by default** and expose arbitrary command execution only during a root-enabled time window.

## Hosts

- `edge1` — arbitrary command execution through the existing root-backed Edge1 Agent Shell.
- `business159` — arbitrary account-level command execution as the authenticated WW.CX Business159 principal (`wwcxjywl`). This is not root on the shared host.

No SSH key, MCP bearer token, or hosting credential is exposed to Ava or the browser.

## Enabling a shell

Run on Edge1 as root:

```text
ava-shellctl enable edge1 --minutes 15 --actor <operator> --reason <reason> [--ticket <id>]
ava-shellctl enable business159 --minutes 15 --actor <operator> --reason <reason> [--ticket <id>]
```

The window is bounded to 1–240 minutes and expires automatically. The two hosts are independent.

After enabling the server-side gate, the authenticated WW.CX admin must put the matching phrase on its own line in the **original user message**:

```text
AVA SHELL EDGE1 APPROVED
```

or

```text
AVA SHELL BUSINESS159 APPROVED
```

The website derives `operator_shell_hosts` only from the raw user message before any library, mail, GitHub, Notion, Airtable, or other retrieved context is appended. Retrieved content therefore cannot activate shell mode.

## Disabling and status

```text
ava-shellctl status
ava-shellctl disable edge1 --actor <operator>
ava-shellctl disable business159 --actor <operator>
```

Disable a shell as soon as the attended task is complete; do not rely solely on TTL expiry.

## Enforcement layers

A shell call succeeds only when all of these are true:

1. the root-controlled host gate exists, is privately owned, and has not expired;
2. the original authenticated admin message supplied the exact host authorization phrase;
3. the gateway request carries `operator:shell:escape` and the requested host;
4. the gateway exposes only that host's raw-shell tool;
5. the broker receives `confirmed=true` for the attended raw-shell capability;
6. the underlying authenticated Edge1 or Business159 execution transport succeeds.

Every gate change and broker invocation is auditable. Shell output remains bounded and redacted by the existing operator transports where applicable.
