# Edge1 SNMP + AI Operations Runbook

## Preflight

Run the authenticated Edge1 operator preflight before mutation. Confirm host/principal, `/opt/edge1-management-interface` branch and dirty state, current listeners, firewall state, installed Net-SNMP utilities, systemd state, available telemetry/database components, disk headroom and trusted management networks. Confirm the accepted `bigbird-ai-gateway.service` remains loopback-only on `127.0.0.1:8787`. Preserve unrelated work. Repository `main` is not guaranteed to match every production checkout.

For an operator-console deployment also confirm the existing authenticated Edge1 adapter on loopback, the active HTTPS virtual host/proxy route, session issuer compatibility, and the exact public Operations Center files that will be backed up.

## Staged installation

The SNMP installer creates timestamped rollback material for existing SNMP configuration/state and systemd units. It deliberately does **not** enable/start services, configure `snmptrapd`, modify the firewall, create SNMP device credentials, or copy Private AI secret values.

```bash
sudo /opt/edge1-management-interface/deploy/install-edge1-snmp.sh
sudo python3 -m json.tool /etc/edge1-snmp/config.json >/dev/null
sudo systemd-analyze verify /etc/systemd/system/edge1-snmp-api.service /etc/systemd/system/edge1-snmp-poller.service /etc/systemd/system/edge1-snmp-poller.timer
```

## Credential provisioning

Provision one root-readable profile per managed identity under `/etc/edge1-snmp/profiles/` with mode `0600`. Prefer SNMPv3 authPriv. Inventory and browser UI receive only the profile reference. Never place passphrases in Git, shell history, documentation, logs, browser storage, AI requests, or acceptance records.

For model-backed SNMP analysis, provide the existing Private AI gateway signing identity to the SNMP API service through the approved Edge1 secret mechanism. Do not duplicate or print those values merely for this service. The SNMP AI adapter refuses non-loopback gateway URLs and sends only sanitized operational evidence.

## Authenticated Operations Center architecture

The full SNMP operator console is served at `/edge1-ops/snmp/` through the existing Edge1 authenticated session adapter. Browser API traffic uses `/edge1-ops/api/v1/snmp...`; the adapter signs allowlisted requests to the loopback SNMP API. The browser never receives the HMAC secret and never contacts `127.0.0.1:8112` or the BigBird listener directly.

The public `/edge1-status/operations-center/snmp.html` path is only an authentication handoff page. `deploy/operations-center/publish.sh` must never copy the full console source into the public status tree.

Read access requires the existing `edge1.security.read` scope. POSTs require same-origin and CSRF state. State-changing SNMP operations additionally require `edge1.security.validate`; downstream deterministic policy remains authoritative. SNMP SET is not exposed as a casual UI operation.

## Controlled backend validation

1. Add only a known authorized management endpoint.
2. Verify SNMPv3 authPriv GET outside the service without leaking command/history secrets.
3. Run one poll cycle and confirm device/interface/metric persistence and retention behavior.
4. Confirm 64-bit counters are preferred when available and reset/reboot samples do not produce bandwidth spikes.
5. Configure `snmptrapd` only after inspecting listener state and only when a concrete authorized trap source exists.
6. Verify event persistence, acknowledgement/deduplication and correlation using controlled evidence.
7. Exercise deterministic incident correlation and verify confirmed versus inferred topology remains distinct.
8. Call the SNMP AI query path and verify it remains on the accepted loopback BigBird gateway, returns provenance, and excludes credential-bearing fields from the model prompt.
9. If SET is ever required, use only a specifically approved lab device after both global and per-device write gates are enabled. SET remains a privileged network change and is not an automatic API action.
10. Confirm service errors, status exports, API output, audit data and AI requests contain no secret values.

## Operator-console validation

Before deployment, run repository tests on the exact PR head and record the CI run identifiers. Then stage the authenticated proxy routes and validate Apache configuration before reload.

After an approved deployment verify:

```text
unauthenticated browser -> rejected
authenticated browser -> /edge1-ops/snmp/ renders
browser -> /edge1-ops/api/v1/snmp/health -> authenticated sanitized JSON
browser POST without valid CSRF -> rejected
insufficient mutation scope -> 403
adapter -> 127.0.0.1:8112 -> allowlisted HMAC request only
SNMP API -> BigBird -> 127.0.0.1:8787 only
```

Also verify the public SNMP path contains only the handoff page, browser-visible payloads contain no secret-bearing fields, the AI response distinguishes deterministic evidence from inference, audit records the authenticated operator, and unrelated services retain their prior healthy state.

## Firewall boundary

Do not modify firewall policy merely to deploy the UI. Ports `8112` and `8787` remain loopback-only. Do not expose UDP/161 or UDP/162 for UI testing. Any later trap-listener or agent change is a separate approved network-management change with its own rollback evidence.

## Operations Center publication

The publisher installs the main public Operations Center status page, rewrites its SNMP link to the authenticated route, backs up the prior public files, and installs only a small SNMP authentication handoff page at the historical static location.

```bash
sudo /opt/edge1-management-interface/deploy/operations-center/publish.sh
curl --fail --silent http://127.0.0.1/edge1-status/operations-center/snmp.html
```

The returned static page must not contain live SNMP inventory, telemetry, AI results, credentials, or the full operator JavaScript application.

## Enablement

Enable the SNMP API/poller only after the corresponding backend acceptance gate is satisfied. The authenticated UI route does not justify enabling polling, a trap listener, or an SNMP agent by itself.

```bash
sudo systemctl enable --now edge1-snmp-api.service
sudo systemctl enable --now edge1-snmp-poller.timer
systemctl is-active edge1-snmp-api.service
systemctl is-active edge1-snmp-poller.timer
ss -lntup | grep -E '(:8112|:8787|:161|:162)'
curl --fail --silent http://127.0.0.1:8112/api/snmp/health
```

The control API must remain loopback-only.

## Acceptance checklist

Configuration parses; exact-head repository tests and CI pass; authenticated console access works; unauthenticated/insufficient-scope/invalid-CSRF cases fail correctly; browser never receives HMAC or credential material; SNMPv3 authPriv GET/WALK succeeds against an authorized device; legacy protocol never appears without explicit approval; controlled SET is rejected unless both gates pass; 64-bit counter/reset/reboot behavior is correct; telemetry persists; retention stays bounded; topology does not fabricate links; incident correlation preserves evidence confidence; model-backed AI uses only the accepted loopback BigBird gateway and sanitized evidence; action proposals remain policy bounded; audit distinguishes human/deterministic/AI involvement and attributes the operator; public status publication contains only the SNMP handoff; unrelated Edge1 services remain healthy.

## Rollback

Stop/disable only directly affected SNMP units if they were enabled, restore `/etc/edge1-snmp/config.json` only if it changed, restore the prior authenticated-adapter runtime and Apache route from the recorded backup, restore the backed-up public Operations Center/handoff files, validate configuration, and restart/reload only directly affected services. Verify previous authenticated security-console behavior, loopback listener state and unrelated-service health. Preserve the SQLite database and acceptance evidence unless an explicit approved restore procedure requires replacement. Never include secret values in rollback records.
