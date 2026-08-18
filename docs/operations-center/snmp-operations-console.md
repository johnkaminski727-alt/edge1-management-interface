# SNMP Operations Console Runbook

## Purpose

Operate the WW.CX Edge1 SNMP + AI console through the authenticated Operations Center boundary without exposing SNMP credentials, the SNMP API HMAC secret, BigBird credentials, or loopback management listeners.

## Trust boundary

`browser -> HTTPS reverse proxy -> Edge1 authenticated operator adapter on loopback -> HMAC-signed SNMP API on 127.0.0.1:8112 -> sanitized evidence -> BigBird on loopback`

The browser must never contact ports 8112 or 8787 directly and must never receive signing material.

## Operator access

Use `/edge1-ops/snmp/` after establishing the normal Edge1 operator session. The public status-tree path `/edge1-status/operations-center/snmp.html` is only an authentication handoff and must never contain the full console or live SNMP data.

Read visibility requires the existing `edge1.security.read` scope. POSTs require same-origin and CSRF state. State-changing SNMP operations additionally require `edge1.security.validate` and remain subject to downstream deterministic policy.

## Normal workflows

### Overview

Use Overview to answer network health, attention and next-investigation questions. Treat badges and counters as deterministic state where backed by the API. Treat BigBird prose as interpretation and verify it against the displayed evidence/provenance.

### Device investigation

Open Devices, filter or search, then select a device. Review identity, current health, interfaces, telemetry, related events and alerts. Device-specific BigBird questions should include the device identifier in context.

### Incidents

Use Incidents to correlate observations over a bounded time window. Preserve the distinction between observed events, derived correlations and AI interpretation. Never convert an AI inference into a verified fact without supporting evidence.

### MIB / OID

Use the MIB / OID Explorer for authoritative local object information. BigBird may explain an OID, but it does not replace MIB metadata.

### Actions

Only allowlisted action proposals are available. AI may recommend a proposal; deterministic policy decides whether it is permitted. SNMP SET remains disabled unless separately and intentionally enabled by both global and per-device policy gates. The console does not expose arbitrary command execution.

## Discovery and onboarding

1. Enter an explicit authorized host or approved CIDR.
2. Select or enter an existing credential **reference name** only.
3. Run the dry-run/boundary preview.
4. Probe only when the target is authorized and the discovery boundary is correct.
5. Review discovered identity before creating a managed-device record.
6. Onboard using SNMPv3 authPriv by default. Any v1/v2c use requires explicit legacy approval and is never a silent downgrade.
7. Confirm the resulting managed device and audit record.

Do not create credentials in the browser. Do not display or copy stored authentication/privacy passphrases into the UI.

## Empty inventory

Zero devices is a valid state. The console should show the SNMP platform as ready where applicable, zero devices/profile references, BigBird availability, polling not enabled and SNMP SET disabled. Do not create fake production devices for UI testing.

## Pre-deployment checklist

- confirm the intended branch/head and clean deployment source;
- back up affected authenticated-adapter, Apache and public Operations Center files;
- run repository tests on the exact head;
- validate the Apache configuration before reload;
- confirm ports 8112 and 8787 remain loopback-only;
- confirm no firewall, DNS, SSH or unrelated authentication changes are included;
- confirm the public publisher will install only the SNMP authentication handoff page;
- record the rollback directory and exact previous service/runtime state.

## Live validation

After an approved deployment:

- unauthenticated `/edge1-ops/snmp/` is rejected;
- authenticated console access succeeds;
- read API requests require the operator session;
- mutation requests without correct CSRF fail;
- insufficient scope fails with 403;
- SNMP adapter accepts only allowlisted paths;
- browser-visible responses contain no credential values or signing material;
- deterministic empty-inventory state renders correctly;
- BigBird query succeeds through UI -> adapter -> SNMP API -> BigBird when the model is available;
- deterministic evidence remains visible if model interpretation fails;
- audit identifies the authenticated operator;
- the public SNMP status path contains only the handoff page;
- unrelated services remain healthy;
- SNMP API and BigBird remain loopback-only;
- rollback remains immediately available.

## Real-device acceptance

A real-device gate requires a known authorized SNMPv3 authPriv endpoint and securely provisioned credential profile. Validate controlled GET, WALK/BULK and application polling, then confirm interface/metric persistence, alerts/incidents and topology against observed device state. Test traps/informs only with a concrete authorized source/target. Do not broadly expose UDP/162 and do not install or enable `snmpd` merely to manufacture an acceptance target.

## Rollback

Restore the backed-up public Operations Center/handoff files, restore the prior authenticated-adapter runtime and Apache route configuration, validate configuration, restart/reload only directly affected services, and verify previous console behavior plus unrelated-service health. Preserve the evidence directory and audit record; never put secret values into rollback notes.
