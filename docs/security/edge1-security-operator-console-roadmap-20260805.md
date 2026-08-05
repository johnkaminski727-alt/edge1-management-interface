# Edge1 Security Service Console roadmap

Date: 2026-08-05  
Target route: `/edge1-ops/security/`  
Current state: repository prototype; not deployed

## Objective

Provide a human operator with a normal browser interface for the managed Edge1 security sensor. The operator should not need to construct API requests, signatures, shell commands, service names, or JSON payloads.

The console should answer four questions clearly:

1. Is the managed sensor running and receiving traffic?
2. What security events need attention?
3. What safe maintenance actions are available?
4. What happened after an action, and where is the evidence?

## Existing foundations

The following foundations already exist:

- managed Suricata service: `wwcx-network-sensor-suricata.service`;
- full PCAP recorder: `wwcx-network-sensor-pcap.service`;
- human-readable telemetry: `/edge1-status/security-operations.json`;
- live read-only Security Operations page: `/edge1-status/security/`;
- loopback-only allowlisted operations API;
- registered operations for configuration validation, rule reload, and log rotation;
- HMAC authentication, nonce replay protection, bounded execution, and SQLite audit at the machine-client boundary;
- a disabled browser authentication and session policy for `/edge1-ops/`.

The browser must not call the loopback operations API directly and must never receive the HMAC signing secret. A future server-side browser gateway will translate an authenticated, authorized browser request into the existing allowlisted operation.

## Phase 1 — Human interface foundation

Implemented in the repository:

- `src/web/edge1-ops/security/index.html`;
- `config/security/edge1-security-operator-console.json`;
- `tests/validate_security_operator_console.py`.

The prototype provides:

- plain-language sensor health;
- live read-only telemetry when the status feed is available;
- understandable action descriptions;
- expected effects, success results, and failure behavior;
- typed-confirmation previews for controlled changes;
- recent evidence display;
- an explicit lock notice explaining why production actions are not yet enabled;
- a planned restart-sensor workflow with automatic post-restart capture acceptance.

No live route, authentication, service, API, network, firewall, DNS, sensor, or traffic-control change is made in this phase.

## Phase 2 — Authenticated browser boundary

Requires explicit production authentication authorization.

The restricted browser boundary must provide:

- OpenID Connect authorization-code flow;
- PKCE `S256`;
- MFA verification;
- trusted issuer and audience validation;
- server-side sessions;
- opaque browser session identifiers;
- `Secure`, `HttpOnly`, and `SameSite=Strict` cookies;
- CSRF protection for action requests;
- per-action scopes;
- rate limits;
- append-only browser audit;
- no anonymous fallback.

The repository already contains a provider-neutral, disabled policy and an Apache design artifact. An identity provider, adapter, and session store must be selected and verified before activation.

## Phase 3 — Server-side operator gateway

The gateway will be the only component allowed to communicate with the loopback operations API on behalf of a browser session.

Required behavior:

- accept only exact action identifiers defined by policy;
- accept no command text, service name, path, URL, or arbitrary parameters;
- obtain actor identity from the verified browser session;
- create the machine-client signature on the server;
- use one-time nonces and bounded timestamps;
- preserve the existing operations API audit event identifier;
- return a normalized, human-readable result;
- strip secrets, internal signing fields, and unbounded command output;
- fail closed when authentication, authorization, CSRF, audit, or API health is unavailable.

## Phase 4 — Enable safe actions incrementally

### First live action: Check the security configuration

Action: `security.validate_config`  
Risk: read-only

Acceptance:

- one clear confirmation button;
- visible progress state;
- pass or needs-attention result;
- no restart or configuration change;
- evidence identifier and timestamp;
- audit record tied to the authenticated operator.

### Second live action: Load updated detection rules

Action: `security.rules.reload`  
Risk: controlled change

Acceptance:

- type `LOAD RULES`;
- verify the managed service is active before submission;
- use the reviewed `SIGUSR2` reload contract;
- verify the service remains active;
- verify fresh EVE statistics after the request;
- record evidence and recovery guidance;
- enforce a cooldown to prevent repeated reloads.

### Third live action: Rotate security logs now

Action: `security.logs.rotate`  
Risk: controlled change

Acceptance:

- type `ROTATE LOGS`;
- verify the intended managed log path;
- preserve existing files;
- verify a current writable log after rotation;
- record before-and-after metadata and evidence.

## Phase 5 — Additional human operations

Potential additions, each requiring a separate allowlisted backend action and acceptance contract:

- restart the managed sensor;
- update detection rules from an approved pinned source;
- view service logs with privacy filtering;
- view packet and event counter history;
- manage metadata and PCAP retention;
- create an incident note from an alert;
- export a bounded evidence package;
- temporarily suppress a reviewed noisy rule with automatic expiry;
- compare configuration and rule changes before applying them.

A stop or disable control should not be exposed as an ordinary convenience action. Emergency or maintenance shutdown requires a separate high-risk workflow with explicit impact language and recovery steps.

## Interface requirements

The console must use ordinary language first. Technical details can remain available under an expandable section.

Each action must show:

- what it does;
- why an operator might use it;
- what it changes;
- what it does not change;
- expected duration;
- confirmation requirement;
- progress;
- success result;
- failure result;
- evidence identifier;
- recovery guidance.

Buttons must never silently issue repeated requests. The browser should disable the submitted action until the first request completes or times out.

## Current safety boundary

The prototype is intentionally locked. It does not:

- deploy `/edge1-ops/security/`;
- choose or configure an identity provider;
- create credentials or sessions;
- expose an API secret to the browser;
- enable mutations;
- add a listener;
- alter Apache;
- restart or reload the sensor;
- change rules, logs, retention, firewall, DNS, WireGuard, routes, NAT, or traffic controls.

## Recommended next implementation

Build and test the provider-neutral server-side browser gateway and session adapter behind a denied-by-default local staging route. Keep the production route disabled until the actual identity provider and Apache OIDC adapter are inventoried and explicitly authorized.
