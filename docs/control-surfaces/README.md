# Edge1 Control Surfaces

Date: 2026-08-18
Status: repository foundation; live inventory and activation pending authenticated Edge1 execution

## Purpose

Provide the WW.CX Edge1 Operations Center with a bounded, read-only view of Edge1 control-plane surfaces without exposing SSH, databases, AMI, ARI, arbitrary Asterisk CLI, arbitrary Kamailio RPC, arbitrary shell commands, backend URLs, or ports to a browser or external AI provider.

This foundation intentionally does **not** change Apache, nftables, listener bindings, FreePBX, Asterisk, Kamailio, certificates, authentication, DNS, carrier routing, media paths, or production traffic. Those changes require fresh authenticated host evidence first.

## Architecture

```text
Authenticated WW.CX Operations Center
  -> server-side HMAC Edge1 Operations bridge
  -> loopback-only Edge1 Operations API (fixed action names)
  -> fixed read-only diagnostic profiles
       +-- listener inventory and conservative classification
       +-- Asterisk allowlisted diagnostics
       +-- Kamailio allowlisted diagnostics
       +-- FreePBX status
       +-- existing telephony health
  -> bounded/redacted results
```

The browser never selects a command, backend URL, host, port, file path, or shell fragment. The new operations actions accept no parameters.

## Surface classes

Every discovered listener is placed in exactly one class:

- `public-infrastructure`
- `peering`
- `private-control`
- `internal-service`
- `unknown-needs-attribution`

Classification is deliberately conservative. A wildcard/public listener is not automatically a defect, and an Asterisk SIP listener is not automatically preserved as peering. Unknown surfaces stay unchanged until owner, purpose, consumers, dependencies, and rollback consequences are established.

## Read-only diagnostic profiles

`server/control_surface_diagnostics.py` accepts only these exact profiles:

- `summary`
- `listeners`
- `asterisk`
- `kamailio`
- `freepbx`

Asterisk commands are fixed to:

- `core show uptime`
- `core show channels`
- `pjsip show endpoints`
- `pjsip show transports`
- `pjsip show registrations`
- `module show`
- `http show status`

Kamailio uses fixed `kamcmd` status calls. FreePBX uses `fwconsole status`. Output is bounded and common secret-bearing fields are redacted before JSON output.

## Operations API actions

The operations allowlist adds only non-mutating actions:

- `control_surfaces.summary`
- `control_surfaces.listeners`
- `asterisk.diagnostics`
- `kamailio.diagnostics`
- `freepbx.diagnostics`

The existing API continues to reject request parameters and keeps `EDGE1_OPS_MUTATIONS_ENABLED=false` in the supplied unit.

## Native administrative sessions

FreePBX Administration and UCP are represented as `CLOSED` in the browser foundation. No session-opening endpoint exists in this increment.

A future native-session broker must satisfy all of the following before the button can be enabled:

1. authenticated authorized operator only;
2. same-origin or reviewed private reverse-proxy route;
3. backend remains loopback/private and never opens a WAN listener;
4. explicit short expiry and server-side revocation;
5. no arbitrary backend URL or port from browser input;
6. CSRF protection for session state changes;
7. audit event for open, launch and close;
8. compatible handling of redirects, cookies, WebSockets, CSP, `X-Frame-Options`, and FreePBX path assumptions;
9. before/after listener and firewall verification;
10. tested rollback.

## Public `edge1.ww.cx` behavior

The required ordinary public destination is:

```text
https://creekco.ca/time/
```

No Apache redirect is committed by this foundation because current vhost ordering, certificate identity, aliases/proxies, and service-specific routes must be freshly inventoried first. The Operations Center therefore reports redirect state as `unverified`, not `failed` or `complete`.

## Private AI boundary

Control Surfaces is compatible with the accepted private BigBird AI gateway pattern: provider requests are mediated by private, allowlisted tools rather than provider-to-machine access.

The diagnostic actions are appropriate future read-only AI tools because their command set and parameters are fixed server-side. Enabling a provider adapter must not grant new machine permissions; provider selection and model routing remain separate from tool authorization.

No provider API keys, passwords, HMAC values, cookies, certificates, private keys, raw AMI/ARI access, or arbitrary shell access belong in the browser, model prompt, repository, or audit payload.

## Fresh live activation gate

Before any exposure-reduction or proxy change, capture a current authenticated inventory of:

- TCP and UDP listening sockets, owning processes and bind addresses;
- Apache version/modules/vhosts/includes/aliases/proxies/default-host behavior and `apachectl configtest`;
- nftables ruleset;
- WireGuard state;
- FreePBX services and routes;
- Asterisk HTTP/HTTPS/WSS, AMI, ARI, PJSIP, RTP/media transports;
- Kamailio listeners/routing;
- database and Node listeners;
- DNS/resolver listeners;
- current authentication/proxy services;
- TLS certificates relevant to Edge1 virtual hosts;
- active SIP/telephony dependencies;
- Operations API and private AI services.

Where tooling permits, also perform outside-in reachability checks from an independent network. Sandbox or connector restrictions are not evidence that a port is closed.

## Production change sequence after inventory

For each supported change: record current state, dependencies and rollback; create a timestamped backup; validate syntax; preflight; apply the smallest change; reload/restart only directly affected services; verify listeners, firewall, authentication, public infrastructure and peering; inspect fresh logs; preserve evidence; then continue.

Expected priority after a fresh inventory is:

1. prove required public infrastructure and SIP/media dependencies;
2. constrain management-only listeners to loopback/WireGuard/private interfaces where evidence supports it;
3. close unintended WAN management reachability without altering carrier routing or emergency behavior;
4. install the intentional public Edge1 redirect without affecting service-specific vhosts;
5. design and validate an authenticated temporary FreePBX session broker;
6. keep AI access read-only/allowlisted by default and independently auditable.

## Validation

Repository validation for this foundation is provided by `tests/test_control_surface_diagnostics.py`, `tests/test_control_surfaces_allowlist.py`, and `.github/workflows/control-surfaces.yml`.

Passing repository tests prove only the code/policy contract. They do not prove current Edge1 listener state, firewall behavior, Apache routing, peering preservation, or live deployment.
