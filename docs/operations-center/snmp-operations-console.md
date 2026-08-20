# SNMP Operations Console Runbook

## Purpose

Operate the WW.CX Edge1 SNMP + AI console through the authenticated Operations Center boundary without exposing SNMP credentials, the SNMP API HMAC secret, BigBird credentials, or loopback management listeners.

## Trust boundary

`browser -> HTTPS reverse proxy -> Edge1 authenticated operator adapter on loopback -> HMAC-signed SNMP API on 127.0.0.1:8112 -> sanitized deterministic evidence -> BigBird on loopback`

The browser must never contact ports 8112 or 8787 directly and must never receive signing material.

## Operator access

Use `/edge1-ops/snmp/` after establishing the normal Edge1 operator session. The public status-tree path `/edge1-status/operations-center/snmp.html` is only an authentication handoff and must never contain the full console or live SNMP data.

Read visibility requires the existing `edge1.security.read` scope. POSTs require same-origin and CSRF state. State-changing SNMP operations additionally require `edge1.security.validate` and remain subject to downstream deterministic policy.

## Normal workflows

### Overview

Use Overview to answer network health, attention and next-investigation questions. The console distinguishes `FRESH`, `DEGRADED`, `STALE`, `AUTH REQUIRED`, and `ACCESS DENIED`; a partially unavailable backend must not be rendered as a healthy empty system. Treat badges and counters as deterministic state where backed by the API. Treat BigBird prose as interpretation and verify it against displayed evidence/provenance.

### Device investigation

Open Devices, filter or search, then select a device or use `#devices/<device-id>` as a deep link. Review identity, current health, SNMP version, interfaces, numeric telemetry trends, raw recent samples and device-specific BigBird investigation. IF-MIB numeric status values are normalized for operator display (`1=up`, `2=down`, etc.).

### Alerts and events

Alerts and Events provide searchable tables plus expandable evidence/detail drawers. Preserve timestamps, correlation identifiers, normalized event information and safe event/alert evidence. Never surface credential-bearing before/after data.

### Incidents

Use Incidents to correlate observations over a bounded time window. Preserve the distinction between observed events, derived correlations and AI interpretation. Never convert an AI inference into a verified fact without supporting evidence.

### Topology

Topology consumes the backend evidence model directly: managed devices are nodes and `local_device_id` / `remote_device_id` relationships are edges. Confirmed relationships are solid; inferred relationships are dashed. Active alert/degraded state may highlight affected nodes/links. Selecting a relationship opens its evidence. A remote identifier that is not a managed node remains in the relationship table rather than becoming a fabricated managed device. If evidence is insufficient, the console explicitly reports that no topology evidence exists.

### MIB / OID

Use the MIB / OID Explorer for authoritative local object information. BigBird may explain an OID, but it does not replace MIB metadata.

### Actions

Only allowlisted action proposals are available. AI may recommend a proposal; deterministic policy decides whether it is permitted. SNMP SET remains disabled unless separately and intentionally enabled by both global and per-device policy gates. The console does not expose arbitrary command execution.

## Discovery and onboarding

The normal browser onboarding path is intentionally **SNMPv3-only** and does not contain a casual legacy-approval control.

1. Enter an explicit authorized host or approved CIDR.
2. Enter an existing credential **reference name** only.
3. Run the bounded dry-run preview.
4. The backend resolves the actual protocol version of that credential profile. The normal UI refuses to continue unless it is SNMPv3.
5. Explicitly approve the SNMPv3 probe.
6. Review discovered management address, sysName, sysObjectID, location and probe outcome.
7. Select **Onboard device** only for an intended, successfully probed SNMPv3 device.
8. The API validates the actual credential-profile version again and refuses a declared/profile mismatch before the managed-device record is created.
9. Confirm the new device record and audit attribution.

Legacy v1/v2c support exists only for separately authorized cases. The API requires an explicit legacy approval flag from a non-casual approved caller; the standard Operations Console does not send that flag. There is no silent downgrade and discovery no longer hardcodes devices as SNMPv3 when the underlying profile is legacy.

Do not create credentials in the browser. Do not display or copy stored authentication/privacy passphrases into the UI.

## AI behavior

BigBird status begins as `not checked`; it is not labeled available until a model-backed request actually succeeds. Model output is displayed separately from verified observations, derived metrics, deterministic rule results, confidence, evidence, recommendations and provenance.

If the model provider returns a service-unavailable result with deterministic evidence, the console labels BigBird unavailable and still presents the deterministic evidence. This fallback is an acceptance requirement, not an error-hidden empty state.

## Empty inventory

Zero devices is a valid state. The console should show zero devices and meaningful empty states without creating fake production devices. A successful backend with zero inventory is distinct from a degraded/unavailable backend. Do not create fake production devices for UI testing.

## Repository validation

The repository workflow runs every `tests/validate_*.py` file. The SNMP console validation wrapper additionally runs the focused UI/client tests and extracts the single embedded console script for `node --check` syntax validation. Discovery-security regressions verify actual profile-version reporting, legacy refusal, and declared/profile mismatch rejection.

Exact final CI results are recorded in PR #413 checks/metadata. Do not substitute an earlier passing head for the exact final head.

## Pre-deployment checklist

- an approved authenticated Edge1 Live Shell/operator path is available;
- confirm host/principal and current Edge1 checkout, branch/head, dirty state and unrelated work;
- inspect current authenticated-adapter, Apache vhost/proxy, public Operations Center and SNMP runtime state;
- record current services/listeners, especially 8108, 8112 and 8787;
- create timestamped backups of every authenticated-adapter, Apache and public Operations Center file that will change;
- run repository tests on the exact head and confirm final GitHub CI;
- validate the Apache configuration before any reload;
- confirm ports 8112 and 8787 remain loopback-only;
- confirm no firewall, DNS, SSH, certificate or unrelated authentication changes are included;
- confirm the public publisher will install only the SNMP authentication handoff page;
- record rollback locations and exact prior service/runtime state.

## Live deployment boundary

Deploy only the intended authenticated proxy surfaces:

- `/edge1-ops/snmp/`
- `/edge1-ops/api/v1/snmp...`

These routes proxy to the existing loopback authenticated adapter, not directly to port 8112 or 8787. Validate the staged Apache configuration before applying it and validate the effective Apache configuration again afterward. Restart/reload only directly affected services.

Do not enable polling, `snmpd`, `snmptrapd`, UDP/161 or UDP/162 merely to deploy the operator UI.

## Live validation

After an approved deployment:

- unauthenticated `/edge1-ops/snmp/` is rejected;
- unauthenticated browser API requests are rejected;
- authenticated console access succeeds;
- read API requests require the operator session/read scope;
- mutation requests without correct same-origin/CSRF state fail;
- insufficient mutation scope fails with 403;
- SNMP adapter accepts only allowlisted paths and never forwards arbitrary URLs;
- browser-visible responses contain no credential values, communities, passphrases, HMAC signing material, relay/API secrets or private keys;
- deterministic empty-inventory state renders correctly when the backend is healthy;
- unavailable backend state renders `DEGRADED`/error rather than a false healthy empty system;
- a successful BigBird query traverses UI -> authenticated adapter -> HMAC loopback SNMP API -> deterministic evidence -> loopback BigBird -> structured response;
- deterministic evidence remains visible if model interpretation fails;
- audit identifies the authenticated operator;
- the public historical SNMP status path contains only the handoff page;
- no direct public listener appears on 8112 or 8787;
- unrelated Edge1 services retain their prior healthy state;
- rollback remains immediately available.

## Real-device acceptance

A real-device gate requires a known authorized SNMPv3 authPriv endpoint and securely provisioned credential profile. Search project records first; a device network-information document alone does not constitute authorization or provide a credential profile.

When an authorized endpoint/profile exists, validate controlled GET and WALK/BULK, then application polling, interface/metric persistence, alert/incident behavior and topology against observed device state. Test traps/informs only with a concrete authorized source/target. Do not broadly expose UDP/162 and do not install or enable `snmpd` merely to manufacture an acceptance target.

If no authorized endpoint/profile exists, record that as the external acceptance blocker and stop the real-device portion without inventing credentials or downgrading protocols.

## Current execution note

As of the 2026-08-18 repository completion pass, the current ChatGPT session did not expose the dedicated authenticated `edge1-live-shell` connector, so the authenticated UI deployment/live-validation steps in this runbook were **not** executed by that pass. Previously recorded backend acceptance remains historical backend evidence only. The live UI gate must be resumed through the approved Edge1 Live Shell connector.

## Rollback

Restore the backed-up public Operations Center/handoff files, restore the prior authenticated-adapter runtime and Apache route configuration, validate configuration, restart/reload only directly affected services, and verify previous console behavior plus unrelated-service health. If an SNMP unit was enabled only for acceptance, stop/disable only that directly affected unit and confirm listener restoration. Preserve databases/evidence unless an explicit approved restore procedure requires replacement. Never put secret values into rollback notes.
