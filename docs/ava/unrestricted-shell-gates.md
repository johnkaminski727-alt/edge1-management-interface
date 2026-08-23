# Ava administrator-controlled unrestricted shell gates

Ava has two independent unrestricted shell escape hatches. They are disabled by default and are controlled from the authenticated **Admin Functions** panel in the WW.CX Ava chat UI.

## Hosts

- `edge1` — arbitrary command execution through the root-backed Edge1 Agent Shell.
- `business159` — arbitrary account-level command execution as the authenticated WW.CX Business159 principal (`wwcxjywl`). This is not root on the shared host.

No SSH key, MCP bearer token, hosting credential, or broker token is exposed to Ava or the browser.

## Admin Functions workflow

An authenticated WW.CX administrator opens **Admin Functions** in Ava's chat header and enables either shell for 15 minutes, 30 minutes, 1 hour, or 4 hours. The UI records desired state and an audit event on Business159. The authenticated Edge1 synchronization service retrieves that desired state over the existing signed worker channel and reconciles the root-owned broker gate.

The chat prompt no longer contains or requires a magic authorization phrase. A shell tool appears to Ava only while the corresponding broker gate is live. The broker re-checks the gate on every raw-shell invocation, so an expired or disabled gate cannot be bypassed by an already-running conversation.

## Routine service actions

The same panel can temporarily grant `operator:actions:routine`. This exposes only the existing bounded Edge1 service status/restart/reload allowlist. It does not grant raw shell or deployment authority.

## Manual recovery

`ava-shellctl` remains available to a root operator for recovery or emergency disablement:

```text
ava-shellctl status
ava-shellctl disable edge1 --actor <operator>
ava-shellctl disable business159 --actor <operator>
```

Manual disablement is always available. For manual recovery enablement, stop the Admin Functions synchronizer first so the UI control plane does not immediately reconcile the gate back to its stored desired state.

## Enforcement layers

A shell call succeeds only when all applicable layers agree:

1. the authenticated WW.CX administrator has an unexpired desired enable state;
2. the signed Edge1 synchronizer has reconciled that state into a private root-owned broker gate;
3. the gateway observes the live broker gate and exposes only that host's shell tool;
4. the broker confirms the gate again at execution time;
5. the underlying authenticated Edge1 or Business159 transport succeeds.

Every UI state change, synchronization result, broker gate change, and shell invocation is auditable. Disable a shell from the panel as soon as the task is complete; TTL expiry is a backstop rather than the preferred closeout.
