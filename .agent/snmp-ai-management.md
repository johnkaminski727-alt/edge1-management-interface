# SNMP + AI Management Workstream

Last updated: 2026-08-18

## Objective

Implement and safely finish the WW.CX / Edge1 SNMP Management and AI Operations Platform as a private-first, AI-first Operations Center product with SNMPv3 authPriv preferred, bounded automation, auditable evidence and no secret values in Git or browser-visible responses.

## Current repository state

- Repository: `johnkaminski727-alt/edge1-management-interface`
- Integration branch: `live/snmp-ai-acceptance-20260818T165539Z`
- Draft PR: `#413`
- Keep the PR draft until exact-head CI, authenticated live UI deployment validation and the remaining real-device gate are independently satisfied.
- Exact final CI status is authoritative in PR #413 checks/metadata; do not infer it from an older commit recorded in this file.

## Backend platform

Implemented before and during the operator-console work:

- SQLite inventory, interface, telemetry, event, alert, MIB, topology, action-proposal and audit stores.
- SNMPv3 authPriv credential-reference model; credential values remain in private root-readable profiles.
- secure Net-SNMP GET/WALK/BULK execution using ephemeral private configuration rather than passphrases in process arguments.
- bounded discovery, traps/events, MIB search/import, deterministic alert evaluation, incident correlation and topology evidence.
- deterministic action classes and audited bounded remediation proposals.
- loopback-only HMAC-authenticated SNMP API on `127.0.0.1:8112` when enabled.
- BigBird Private AI provider through the accepted loopback gateway on `127.0.0.1:8787`, using sanitized deterministic evidence.

Discovery and onboarding now fail closed against protocol mismatch:

- discovery resolves the **actual credential-profile SNMP version** instead of labeling every result as SNMPv3;
- legacy v1/v2c profiles are rejected by the normal API/UI path unless a separate caller supplies explicit legacy approval;
- managed-device creation verifies that the declared SNMP version matches the credential profile before persisting inventory;
- the browser onboarding workflow intentionally provides no casual legacy-approval switch.

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
- state-changing SNMP API operations additionally require existing `edge1.security.validate` scope and a separate mutation-rate bucket.
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

The current console also includes:

- explicit loading/fresh/degraded/stale/auth-required/access-denied states;
- deep-linked device detail;
- numeric IF-MIB status interpretation so `ifOperStatus=2` is actually shown/filterable as down;
- deterministic numeric telemetry trend charts plus raw recent samples;
- alert and event evidence/detail drawers;
- topology rendering against the backend `local_device_id` / `remote_device_id` schema, including confirmed/inferred styling, alert highlighting and relationship evidence detail;
- topology empty states that never fabricate a link;
- a complete guided onboarding path: bounded dry-run -> explicit SNMPv3 scan -> identity review -> explicit managed-device creation;
- structured AI output that separates answer/inference from verified observations, deterministic evidence, derived metrics, deterministic rules, confidence, recommendations and provenance;
- deterministic evidence display when BigBird interpretation is unavailable.

## Security invariants

- The browser never reads the SNMP API secret and never signs HMAC requests.
- No browser request targets port 8112 or 8787 directly.
- No arbitrary upstream URL is accepted by the adapter.
- trap ingestion is not exposed as an operator-browser route.
- credential values, communities, authentication/privacy passphrases, relay keys and API secrets are not returned to the browser.
- credential profile **reference names** may be shown where needed for onboarding.
- legacy SNMP is not silently selected or inferred from a mislabeled profile.
- SNMP SET remains disabled by policy and is not exposed as a casual UI control.
- no arbitrary command execution surface is added.
- Store Admin remains separate from Operations Center.

## Validation status

Previously completed live SNMP **backend** acceptance on 2026-08-18 is recorded in PR #413 and its evidence directories. It covered loopback/HMAC behavior, empty-inventory polling, sanitized publication, BigBird model-backed query, audit attribution, service isolation and teardown with no remaining public SNMP listener. That evidence predates the authenticated UI increment and must not be represented as live UI acceptance.

Repository/CI work performed for the UI increment:

- a first exact-head repository run identified two stale tests that still asserted the retired public-static SNMP model; those assertions were updated to test the authenticated handoff/API model instead of weakening the implementation;
- focused SNMP UI/client suites were added to the `validate_*.py` path so the repository workflow actually executes them;
- embedded console JavaScript is syntax-checked by Node during repository validation;
- discovery security regression tests cover actual profile-version reporting, legacy refusal and device/profile mismatch rejection;
- static UI regressions cover secret/browser boundaries, authenticated routing, topology schema/evidence, explicit v3 onboarding, degraded/auth states, AI deterministic fallback and numeric IF-MIB handling.

The exact **final** head must still be read from PR #413 and both final workflow results must be preserved there after documentation is committed.

## Live execution status

The current ChatGPT execution environment does not expose the dedicated `edge1-live-shell` authenticated MCP connector required for live Edge1 preflight/deployment, and no equivalent approved authenticated shell is available in this session. Therefore this repository pass has **not** inspected or mutated current live Apache/service/public-file state and has not deployed the new authenticated UI routes. Do not claim otherwise.

Once the Edge1 Live Shell connector is available, continue with backup-first preflight and the live checklist in `docs/handoff/edge1-snmp-ai-runbook.md` and `docs/operations-center/snmp-operations-console.md`.

## Real-device acceptance status

Repository, Library/conversation evidence and connected Google Drive were searched for a known authorized SNMPv3 authPriv endpoint/profile. The available project handoffs continue to state that live acceptance has zero provisioned SNMP credential profiles/devices and still requires a known authorized endpoint/profile. Drive searches for `SNMPv3 authPriv` and `SNMP credential profile` returned no matching credential-profile record. A restricted printer network-configuration document exists, but it does **not** establish an authorized SNMPv3 authPriv target or credential profile and must not be treated as one.

Therefore real-device acceptance remains an external gate. Do not manufacture a target, enable `snmpd`, change a router/firewall/authentication setting, invent credentials, or downgrade to v1/v2c just to satisfy it.

## Remaining acceptance gates

1. Complete repository CI on the exact final PR head and preserve final run identifiers in PR #413 metadata.
2. Restore an approved authenticated Edge1 Live Shell execution path to this session.
3. Inspect actual Edge1 checkout/service/proxy/listener state, create timestamped backups of every affected live file, validate staged Apache configuration and verify rollback before mutation.
4. Deploy only authenticated `/edge1-ops/snmp/` and `/edge1-ops/api/v1/snmp...` routes through the existing loopback auth service; do not expose 8112 or 8787 publicly.
5. Verify unauthenticated rejection, authenticated reads, CSRF rejection, 403 scope behavior, sanitized browser JSON, operator audit attribution, public handoff isolation and unrelated-service health.
6. Verify the live UI -> adapter -> SNMP API -> deterministic evidence -> BigBird -> structured response path plus deterministic fallback.
7. Obtain one known authorized SNMPv3 authPriv endpoint/profile, then validate GET/WALK/BULK, polling, interfaces/metrics, alerts/incidents and topology against actual observed device state.
8. Test traps/informs only when a concrete authorized source/target exists and never broadly expose UDP/162 for acceptance.
9. Merge only after the repository, live UI and genuinely required real-device gates agree.

## Rollback

Repository rollback is commit-by-commit because the console work is intentionally split into focused commits. Live rollback must restore the backed-up Operations Center/public handoff files, restore the prior authenticated-adapter runtime and prior Apache route configuration, validate configuration before restart/reload, restart only directly affected services, then verify loopback listeners, unrelated-service health and the previous authenticated security console.

Never store secret values in rollback evidence or documentation.
