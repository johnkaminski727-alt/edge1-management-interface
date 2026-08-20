# Edge1 SNMP + AI Operations Runbook

## Preflight

Use the authenticated Edge1 Live Shell/operator path before any live mutation. Confirm host/principal, `/opt/edge1-management-interface` branch/head and dirty state, current listeners, firewall state, installed Net-SNMP utilities, systemd state, available telemetry/database components, disk headroom and trusted management networks. Confirm the accepted BigBird gateway remains loopback-only on `127.0.0.1:8787`. Preserve unrelated work and do not switch/reset the shared production checkout merely to deploy this workstream.

For the operator-console deployment also inspect the existing authenticated Edge1 adapter, HTTPS virtual host/proxy route, session issuer compatibility, and the exact public Operations Center files that will be backed up.

If the authenticated Edge1 Live Shell connector is unavailable, do not substitute unauthenticated network access, guessed SSH credentials, or public endpoints. Complete repository work only and record live deployment as blocked.

## Staged installation

The SNMP installer creates timestamped rollback material for existing SNMP configuration/state and systemd units. It deliberately does **not** enable/start services, configure `snmptrapd`, modify the firewall, create SNMP device credentials, or copy Private AI secret values.

```bash
sudo /opt/edge1-management-interface/deploy/install-edge1-snmp.sh
sudo python3 -m json.tool /etc/edge1-snmp/config.json >/dev/null
sudo systemd-analyze verify /etc/systemd/system/edge1-snmp-api.service /etc/systemd/system/edge1-snmp-poller.service /etc/systemd/system/edge1-snmp-poller.timer
```

## Credential provisioning and protocol gate

Provision one root-readable profile per managed identity under `/etc/edge1-snmp/profiles/` with mode `0600`. Prefer SNMPv3 authPriv. Inventory and browser UI receive only the profile reference. Never place passphrases in Git, shell history, documentation, logs, browser storage, AI requests, or acceptance records.

Discovery and device creation now resolve the **actual credential-profile protocol**. The normal Operations Console will not proceed with a v1/v2c profile. The API also rejects a device whose declared SNMP version differs from its credential profile. Legacy protocol use requires a separate explicitly authorized caller and must never be a silent downgrade.

For model-backed SNMP analysis, provide the existing Private AI gateway signing identity to the SNMP API service through the approved Edge1 secret mechanism. Do not duplicate or print those values merely for this service. The SNMP AI adapter refuses non-loopback gateway URLs and sends only sanitized operational evidence.

## Authenticated Operations Center architecture

The full SNMP operator console is served at `/edge1-ops/snmp/` through the existing Edge1 authenticated session adapter. Browser API traffic uses `/edge1-ops/api/v1/snmp...`; the adapter signs allowlisted requests to the loopback SNMP API. The browser never receives the HMAC secret and never contacts `127.0.0.1:8112` or the BigBird listener directly.

The public `/edge1-status/operations-center/snmp.html` path is only an authentication handoff page. `deploy/operations-center/publish.sh` must never copy the full console source into the public status tree.

Read access requires the existing `edge1.security.read` scope. POSTs require same-origin and CSRF state. State-changing SNMP operations additionally require `edge1.security.validate`; downstream deterministic policy remains authoritative. SNMP SET is not exposed as a casual UI operation.

## Repository validation

Run the exact PR head through both repository workflows before live deployment. The repository validator executes every `tests/validate_*.py`; the SNMP console validator also runs focused client/UI tests and extracts the embedded console JavaScript for Node syntax validation. Discovery-security tests verify actual profile-version reporting, legacy refusal, and declared/profile mismatch rejection.

Preserve final workflow run IDs in PR #413 metadata. Earlier passing backend heads are not substitutes for final-head validation.

## Backup-first operator-console deployment

Before changing live state, record current configuration and create timestamped backups of all affected files. At minimum inspect/back up:

- authenticated Edge1 adapter runtime/configuration that will change;
- active Apache/HTTPS vhost/proxy configuration that will change;
- `/var/www/edge1-status/index.html` if the publisher will replace it;
- `/var/www/edge1-status/operations-center/snmp.html` if present;
- any directly affected systemd override/unit state.

Validate the staged Apache configuration before applying it. Deploy only these authenticated surfaces through the existing loopback adapter:

```text
/edge1-ops/snmp/
/edge1-ops/api/v1/snmp...
```

Do not proxy browsers directly to 8112 or 8787. Do not add a firewall rule for the UI. Restart/reload only directly affected services, then validate the effective Apache configuration and listeners again.

The public publisher rewrites the public Operations Center SNMP link to `/edge1-ops/snmp/`, backs up prior public files, and installs only a small authentication handoff at the historical SNMP static path:

```bash
sudo /opt/edge1-management-interface/deploy/operations-center/publish.sh
curl --fail --silent http://127.0.0.1/edge1-status/operations-center/snmp.html
```

The returned static page must not contain live SNMP inventory, telemetry, AI results, credentials, or the full operator JavaScript application.

## Authenticated live acceptance

After deployment verify all of the following against current live state:

```text
unauthenticated console/API -> rejected
authenticated browser -> /edge1-ops/snmp/ renders
authenticated read -> succeeds with read scope
browser POST without correct same-origin/CSRF -> rejected
insufficient mutation scope -> 403
adapter -> 127.0.0.1:8112 -> allowlisted HMAC request only
SNMP API -> BigBird -> 127.0.0.1:8787 only
```

Also verify:

- browser-visible payloads contain no community strings, passphrases, HMAC material, relay/API secrets, tokens or private keys;
- empty healthy inventory is distinguishable from a degraded backend;
- numeric IF-MIB status is rendered correctly;
- topology uses recorded `local_device_id` / `remote_device_id` evidence, distinguishes confirmed/inferred relationships and does not fabricate nodes/links;
- alert/event/topology evidence detail is readable without secret leakage;
- BigBird output separates deterministic evidence from inference and deterministic evidence remains visible during model unavailability;
- downstream audit actor identifies the authenticated operator;
- the historical public SNMP URL contains only the authentication handoff;
- ports 8112 and 8787 remain loopback-only;
- unrelated Edge1 services retain their pre-change state.

## Real-device acceptance

Do not manufacture this gate. First identify a **known authorized SNMPv3 authPriv endpoint and its securely provisioned credential profile** from approved records/runtime state.

When one exists:

1. Verify controlled SNMPv3 authPriv GET.
2. Verify WALK/BULK against bounded standard OIDs.
3. Run the application poll cycle.
4. Confirm managed-device, interface and metric persistence.
5. Validate counter/reset/reboot handling against observed state.
6. Exercise deterministic alert/incident behavior with safe evidence.
7. Validate topology only against actual LLDP/CDP or other supported evidence.
8. Test traps/informs only with a concrete authorized source/target and narrow listener/source scope.

A device network-information document by itself is not authorization and is not a credential profile. Do not enable `snmpd`, change router/firewall/authentication state, invent credentials, broadly expose UDP/162, or downgrade to v1/v2c just to produce a passing test.

## Current 2026-08-18 execution state

The repository pass that completed the authenticated console did **not** have access to the dedicated `edge1-live-shell` connector. Therefore current live Apache/service/public-file state was not inspected or mutated by that pass and the authenticated UI has not been live-accepted there. Previously recorded live backend acceptance remains backend evidence only.

Project/Library/Drive searches performed during this pass did not identify a documented authorized SNMPv3 authPriv endpoint/profile. Real-device acceptance therefore remains external until such an endpoint/profile is available.

## Firewall and enablement boundaries

Do not modify firewall policy merely to deploy the UI. Ports `8112` and `8787` remain loopback-only. Do not expose UDP/161 or UDP/162 for UI testing. Any later trap-listener or agent change is a separate approved network-management change with its own rollback evidence.

Enable the SNMP API/poller only after the corresponding backend acceptance gate is satisfied. The authenticated UI route does not justify enabling polling, a trap listener, or an SNMP agent by itself.

## Acceptance checklist

Exact-head repository CI passes; authenticated console access works; unauthenticated/insufficient-scope/invalid-CSRF cases fail correctly; browser never receives HMAC or credential material; discovery/device onboarding fail closed on protocol mismatch; SNMPv3 authPriv GET/WALK succeeds against an authorized device; legacy protocol never appears without explicit approval; controlled SET is rejected unless both global/per-device gates pass; telemetry persists and numerical processing stays deterministic; topology does not fabricate links; incident correlation preserves evidence confidence; model-backed AI uses only loopback BigBird and sanitized evidence; action proposals remain policy bounded; audit distinguishes human/deterministic/AI involvement and attributes the operator; public publication contains only the SNMP handoff; unrelated Edge1 services remain healthy.

## Rollback

Stop/disable only directly affected SNMP units if they were enabled. Restore the recorded prior authenticated-adapter runtime/configuration and Apache route configuration from the timestamped backup, validate Apache configuration, restore the backed-up public Operations Center/handoff files, and restart/reload only directly affected services. Verify the previous authenticated security console, loopback listener state and unrelated-service health. Preserve the SQLite database and acceptance evidence unless an explicit approved restore procedure requires replacement. Never include secret values in rollback records.
