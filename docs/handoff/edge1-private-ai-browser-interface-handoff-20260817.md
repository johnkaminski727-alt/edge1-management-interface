# Edge1 Private AI Browser Interface Handoff

Date: 2026-08-17
Repository: `johnkaminski727-alt/edge1-management-interface`
System: `edge1.ww.cx`

## Executive status

The Private AI backend/gateway milestone is accepted and stable, but the overall user-facing Private AI product is **not complete** because there is not yet a normal browser-accessible chat interface for the operator.

Do not describe the overall Private AI product as complete until an authenticated browser interface is available and usable without SSH tunnelling or direct loopback access.

Current classification:

- backend AI gateway: **accepted / complete for the 0.3.4-alpha.2 milestone**;
- Communications/documentation retrieval: **accepted**;
- Communications provenance and graceful degradation: **accepted**;
- provider-budget remediation: **accepted**;
- signed provider-backed Communications E2E: **accepted**;
- browser-accessible WW.CX Private AI chat interface: **not implemented / next milestone**;
- overall user-facing Private AI product: **incomplete**.

## Accepted backend baseline

Live service:

`bigbird-ai-gateway.service`

Runtime source:

`/opt/bigbird-ai-gateway/app`

Accepted live runtime:

```text
version: 0.3.4-alpha.2
mode: read-only
listener: 127.0.0.1:8787 only
service identity: bigbird-ai:bigbird-ai
main.py SHA-256: 8de2db86fb9eddcb2e2c8f8af51e967672ac00e6cc64229dd3f1939a9770687b
library integrity: ok
indexed documents at acceptance: 63
chunks at acceptance: 501
tool count at acceptance: 6
```

Useful loopback endpoints:

```text
GET  http://127.0.0.1:8787/v1/health
GET  http://127.0.0.1:8787/v1/tools
POST http://127.0.0.1:8787/v1/chat
```

These endpoints are backend/control-plane interfaces, not the final user-facing browser UI.

Protected rollback point:

`/var/backups/bigbird-ai-gateway-reasoning-budget-0.3.4-alpha.2-20260817T065808Z`

## Accepted Communications behavior

All six Communications acceptance requirements are closed:

1. default omission: PASS;
2. missing-scope denial/no leakage: PASS;
3. authorized provider-backed retrieval with provenance: PASS;
4. adversarial retrieved content remains inert/untrusted: PASS;
5. controlled Relay degradation warning/zero results/no retry: PASS;
6. durable signed E2E evidence: PASS.

Final provider-backed acceptance request:

```text
scenario: authorized
group: usenet.comp.lang.python
message/query: Channels
provider request count: 1
retry count: 0
HTTP status: 200
Communications source count: 1
Communications warning: null
E2E_AUTHORIZED=PASS
FINAL_AUTHORIZED_E2E=PASS
```

No additional provider request is required to validate this backend milestone.

## Repository closeout already completed

PR #349 established the living permission/regression contract and was merged as:

`900f85a31d69ec0cbddde4f0387eb660922275f7`

PR #350 completed the Communications provenance/degradation/provider-budget rollout and was squash-merged as:

`c1b2f208617266263050c0fc415374e762d6d1f2`

PR #351 reconciled the durable Private AI state and was squash-merged as:

`7db58630fee725631c953b4721bfff38f4f0e493`

Primary state record:

`.agent/private-ai-chat.md`

Final E2E acceptance record:

`docs/communications/edge1-private-ai-chat-comms-final-e2e-acceptance-20260817.md`

## Next milestone: usable WW.CX Private AI browser interface

The next objective is to make the accepted backend useful through a normal authenticated web interface.

Target product behavior:

- operator opens a normal HTTPS WW.CX URL in a browser;
- authenticated session determines the caller identity/role/scopes;
- a chat UI sends bounded requests through a server-side bridge to the Edge1 Private AI gateway;
- the browser never receives or stores the gateway HMAC signing secret;
- Edge1 gateway remains bound to `127.0.0.1:8787` unless a separately reviewed architecture change explicitly supersedes this;
- the web layer signs/proxies requests server-side or communicates over an approved private authenticated channel;
- user can opt in to Communications/documentation/telephony read tools according to policy;
- source/provenance information is visible in a useful UI;
- read-only and authorization boundaries remain intact;
- provider-cost behavior remains bounded and visible enough for operations.

## Architecture rule

Do **not** solve browser access by exposing raw port `8787` publicly.

Preferred separation remains:

```text
Browser
   |
   v
Authenticated WW.CX web / portal layer
   |
   | private authenticated server-side bridge
   v
Edge1 Private AI gateway
127.0.0.1:8787
```

This preserves the established project separation: public/browser-facing components belong in the web/portal layer; Edge1 remains the private operations/control plane.

## First actions for the next session

1. Re-read `.agent/private-ai-chat.md` and this handoff.
2. Inspect current repository/web portal/interface code before creating anything new.
3. Identify the existing authenticated WW.CX Operations Center or appropriate browser-facing application entry point.
4. Determine where the server-side Edge1 bridge should live and how it will authenticate without exposing secrets to the browser.
5. Define the browser URL and route only after inspecting existing routing/domain conventions; do not invent a public hostname without evidence.
6. Build the smallest usable chat surface first: conversation pane, message input, send/stop state, error handling, source/provenance display, and explicit tool opt-ins.
7. Preserve the existing Edge1 authorization model (`chat:general`, `communications:read`, appropriate role mapping) and fail-closed behavior.
8. Validate with offline/fixture tests before any live provider-backed UI request.
9. Use one bounded live provider request only when needed for final interface E2E acceptance and after the appropriate approval boundary is satisfied.
10. Document the final accessible URL, authentication path, deployment/rollback procedure, and browser-to-Edge1 trust boundary.

## Important product-completion rule

The backend workstream is accepted, but the **overall Private AI product must remain marked incomplete until the browser interface is actually deployed, authenticated, reachable, and demonstrated end to end by the user-facing path**.

A successful localhost API request is not sufficient product acceptance.

## Safety boundaries

Do not expose credentials, HMAC secrets, provider keys, or raw protected evidence.

Do not expose `127.0.0.1:8787` directly to the public Internet as a shortcut.

Do not change DNS, firewall, certificates, authentication policy, public listeners, or production web routing without the appropriate explicit authorization and deployment review.

Do not weaken Communications/tool authorization merely to simplify the browser implementation.

Retrieved content remains untrusted and never grants scopes or write authority.

## Resume sentence

Tomorrow, resume with: **build the authenticated WW.CX browser-facing Private AI chat interface in front of the already accepted Edge1 `0.3.4-alpha.2` backend, keeping port 8787 private and treating the product as incomplete until the browser path is deployed and accepted.**
