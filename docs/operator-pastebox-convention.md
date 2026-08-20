# WW.CX attended operator paste-box convention

Status: durable operator UX and safety convention.

## Purpose

When ChatGPT cannot execute a host command directly and must hand an attended command block to the human operator, the destination must be unmistakable before the operator copies anything. The result destination must be equally explicit.

## Required presentation

Every attended server/workstation paste box must have a visible title immediately above the code block using this form:

```text
SERVER: <fqdn-or-hostname> — <short action>
```

For a local workstation use `WORKSTATION:` or `LOCAL:` instead of `SERVER:`. For Windows commands, identify PowerShell when useful.

The command block itself must begin with a comment banner containing, at minimum:

```text
# SERVER: <fqdn-or-hostname>
# USER:   <expected principal, when known>
# ACTION: <plain-language action>
# SCOPE:  <bounded effect or READ-ONLY>
```

When the assistant is not executing the command itself, the surrounding text must make clear that the block is operator-run / not yet executed.

## Safety rules

- Use one host per paste box. For cross-host work, provide separate numbered paste boxes in execution order.
- Assert the expected hostname inside shell blocks before mutation whenever the host exposes a stable hostname check.
- Assert the expected repository/branch/commit or other reviewed execution state when relevant.
- Keep authorization scope visible. Do not let a broad shell block silently exceed the action named in the title/banner.
- Prefer a child shell or otherwise avoid accidentally terminating the operator's SSH session on an ordinary failed gate.
- Do not place credentials, tokens, private keys, cookies, or other secrets in the block or in requested output.
- A paste box for an approval statement must identify the server/action being approved and state the exact authorized scope and exclusions.

## Result destination

After every operator-run paste box, explicitly say where the resulting information must be deposited. The default is:

```text
Paste the complete terminal output directly back into this ChatGPT conversation.
```

When practical, name stable start/end markers to include. If the command creates protected evidence on the server, state the expected evidence location or explain that the script will report it; do not require the user to upload protected evidence unless it is actually needed.

If the result belongs somewhere else by design, name that exact destination instead of leaving it implicit.

## Example

Visible heading:

```text
SERVER: edge1.ww.cx — Read-only service verification
```

Paste box:

```sh
# ============================================================
# SERVER: edge1.ww.cx
# USER:   wwadmin
# ACTION: Read-only service verification
# SCOPE:  READ-ONLY
# ============================================================

bash <<'EDGE1'
set -u
[ "$(hostname -f)" = "edge1.ww.cx" ] || { echo "STOP: wrong host"; exit 1; }
# bounded commands here
EDGE1
```

Result instruction:

```text
Paste the complete terminal output back into this ChatGPT conversation, from the first verification marker through the final return-code line.
```

This convention is a human-factors safety control, not cosmetic formatting. It should be preserved in future WW.CX attended operator workflows.
