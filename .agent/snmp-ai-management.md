# SNMP + AI Management Workstream

Last updated: 2026-08-18

## Objective

Implement the WW.CX / Edge1 SNMP Management and AI Operations Platform as a private-first, AI-first Operations Center product with SNMPv3 preferred, bounded automation, auditable evidence and no secret values in Git or browser-visible responses.

## Current repository state

- Repository: `johnkaminski727-alt/edge1-management-interface`
- Integration branch: `live/snmp-ai-acceptance-20260818T165539Z`
- Draft PR: `#413`
- Keep the PR draft until exact-head CI, authenticated UI deployment validation and remaining real-device gates are independently satisfied.

## Backend platform

Implemented before the operator-console work:

- SQLite inventory, interface, telemetry, event, alert, MIB, topology, action-proposal and audit stores.
- SNMPv3 authPriv credential-reference model; credential values remain in private root-readable profiles.
- Net-SNMP GET/WALK/BULK execution, deterministic polling, interface collection and counter/rate logic.
- bounded discovery, traps/events, MIB search/import, alert evaluation, incident correlation and topology evidence.
- deterministic action classes and audited bounded remediation proposals.
- loopback-only HMAC-authenticated SNMP API on `127.0.0.1:8112` when enabled.
- BigBird Private AI provider through the accepted loopback gateway on `127.0.0.1:8787`, using sanitized deterministic evidence.

## Operator console architecture

The full SNMP console is not a public static dashboard.

Flow:

`authenticated browser -> Edge1 authenticated operator adapter -> signed loopback SNMP API -> deterministic sanitized evidence -> BigBird Private AI -> structured operator response`

Implementation:

- `src/web/operations-center/snmp.html` is the authenticated console template.
- `server/edge1_security_auth_http_snmp.py` adds the SNMP console and browser API to the existing authenticated Edge1 session boundary.
- `server/edge1_snmp_ui_client.py` is the server-side HMAC client. It accepts only exact loopback origin `http://127.0.0.1:8112`, allowlists paths and methods, bounds query parameters and response sizes, and strips secret-like response fields before browser delivery.
- `server/edge1_security_auth_http.py` routes the SNMP console/API through the existing Edge1 session, scope, CSRF, same-origin, rate-limit and CSP model.
- `server/edge1_security_auth_http_server.py` wires the console template and SNMP API secret path into the existing loopback auth service.
- `deploy/edge1-security-auth/apache-route.conf.example` contains staged reverse-proxy routes only to the loopback authenticated adapter.
- `deploy/operations-center/publish.sh` deliberately does **not** publish the full SNMP console into `/var/www/edge1-status`; it publishes only an authenticated handoff page and rewrites the Operations Center SNMP link to `/edge1-ops/snmp/`.

## Authorization model

- SNMP console and GET visibility require the existing `edge1.security.read` operator scope.
- POST requests require same-origin and valid CSRF state.
- model-backed AI queries use a dedicated action-rate bucket.
- state-changing SNMP API operations additionally require existing `edge1.security.validate` scope and a separate action-rate bucket.
- no new issuer scope names are invented in this change; issuer/session compatibility is preserved.
- operator identity is forwarded as the SNMP API actor so downstream audit records retain attribution.

## Browser-visible product

The console contains deep-linked sections for:

- Overview / NOC dashboard
- Devices
- Interfaces
- Alerts
- Incidents / root-cause correlation
- Topology
- Events / traps
- BigBird AI Assistant
- Discovery / onboarding
- MIB / OID Explorer
- Actions / remediation proposals
- Audit
- Settings / Security Status

The UI includes filtering/search, empty-system states, freshness state, responsive layouts, device detail, telemetry presentation, topology evidence distinction, bounded action proposals and structured AI output. AI output separates answer/inference from verified observations, deterministic evidence, derived metrics, confidence, recommendations and provenance. If AI is unavailable but deterministic evidence is returned, the UI presents that evidence instead of hiding it.

## Security invariants

- The browser never reads the SNMP API secret and never signs HMAC requests.
- No browser request targets port 8112 or 8787 directly.
- No arbitrary upstream URL is accepted by the adapter.
- trap ingestion is not exposed as an operator-browser route.
- credential values, communities, authentication/privacy passphrases, relay keys and API secrets are not returned to the browser.
- credential profile **reference names** may be shown where needed for onboarding.
- SNMP SET remains disabled by policy and is not exposed as a casual UI control.
- no arbitrary command execution surface is added.
- Store Admin remains separate from Operations Center.

## Validation status

Previously completed live SNMP backend acceptance on 2026-08-18 is recorded in PR #413 and its evidence directories. It covered loopback/HMAC behavior, empty-inventory polling, sanitized publication, BigBird model-backed query, audit attribution, service isolation and teardown with no remaining public SNMP listener.

For this operator-console increment:

- local Python compilation passed for the new SNMP UI client and authenticated adapter integration;
- local focused unit/static tests passed before repository publication;
- repository tests were added for exact-loopback signing, path allowlisting, secret sanitization, required UI sections, browser trust boundary and public-publisher separation;
- exact-head GitHub Actions status is a separate gate and must not be inferred from earlier PR runs;
- authenticated live UI deployment has not been performed by this repository update.

## Remaining acceptance gates

1. Run repository CI on the exact final PR head and preserve the run identifiers.
2. Before live deployment, inspect the actual Edge1 checkout/service state, back up affected files, validate the staged Apache configuration, and verify rollback commands.
3. Deploy only the authenticated `/edge1-ops/snmp/` and `/edge1-ops/api/v1/snmp` paths through the existing loopback auth service; do not expose 8112 or 8787 publicly.
4. Verify unauthenticated console/API requests are rejected, authenticated reads succeed, POSTs require CSRF, scope enforcement returns 403 where expected, and browser-visible JSON contains no credential material.
5. Verify UI -> adapter -> SNMP API -> BigBird -> structured evidence response and confirm downstream audit actor attribution.
6. Verify Operations Center and unrelated services remain healthy after the deployment and confirm the public `/edge1-status/operations-center/snmp.html` contains only the authenticated handoff page.
7. Real-device acceptance still requires one known authorized SNMPv3 authPriv endpoint/profile. Do not manufacture a target, enable `snmpd`, alter router/firewall configuration, invent credentials, or downgrade protocols just to satisfy the gate.
8. Validate interface/telemetry/alert/incident/topology behavior against that real authorized device before enabling intended polling timers.

## Rollback

Repository rollback is commit-by-commit because the console work was intentionally split into focused commits. Live rollback must restore the backed-up Operations Center/public handoff files, restore the prior authenticated-adapter service/runtime and prior Apache route configuration, validate configuration before restart/reload, restart only directly affected services, then verify loopback listeners, unrelated-service health and the previous authenticated security console.

Never store secret values in rollback evidence or documentation.
