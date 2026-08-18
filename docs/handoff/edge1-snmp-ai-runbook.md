# Edge1 SNMP + AI Operations Runbook

## Preflight

Run the authenticated Edge1 operator preflight before mutation. Confirm host/principal, `/opt/edge1-management-interface` branch and dirty state, current listeners, firewall state, installed Net-SNMP utilities, systemd state, available telemetry/database components, disk headroom and trusted management networks. Confirm the accepted `bigbird-ai-gateway.service` remains loopback-only on `127.0.0.1:8787`. Preserve unrelated work. Repository `main` is not guaranteed to match every production checkout.

## Staged installation

The installer creates a timestamped rollback copy for any existing SNMP config, private configuration/state directories, an API signing secret only when absent, the SQLite schema, and systemd units. It deliberately does **not** enable/start services, configure `snmptrapd`, modify the firewall, create SNMP device credentials, or copy Private AI secret values.

```bash
sudo /opt/edge1-management-interface/deploy/install-edge1-snmp.sh
sudo python3 -m json.tool /etc/edge1-snmp/config.json >/dev/null
sudo systemd-analyze verify /etc/systemd/system/edge1-snmp-api.service /etc/systemd/system/edge1-snmp-poller.service /etc/systemd/system/edge1-snmp-poller.timer
```

## Credential provisioning

Provision one root-readable profile per managed identity under `/etc/edge1-snmp/profiles/` with mode `0600`. Prefer SNMPv3 authPriv. Inventory receives only the profile reference. Never place passphrases in Git, shell history, documentation, logs, AI requests, or acceptance records.

For model-backed SNMP analysis, provide the existing Private AI gateway signing identity to the API service through the approved Edge1 secret mechanism as `BB_RELAY_KEY_ID` and `BB_RELAY_SECRET`. Do not duplicate or print those values merely for this service. The SNMP AI adapter refuses non-loopback gateway URLs and sends only sanitized operational evidence.

## Controlled validation

1. Add only a controlled management endpoint.
2. Verify SNMPv3 authPriv GET outside the service without leaking command/history secrets.
3. Run one poll cycle and confirm device/interface/metric persistence and retention behavior.
4. Confirm 64-bit counters are preferred when available and reset/reboot samples do not produce bandwidth spikes.
5. Configure an existing or newly installed `snmptrapd` only after inspecting the current listener state; use the traphandle helper.
6. Send a test trap and inform where supported and verify persistence, acknowledgement and duplicate suppression.
7. Exercise a deterministic incident-correlation case and verify confirmed versus inferred topology remains distinct.
8. With the existing BigBird gateway identity available, call the SNMP AI query path and verify the request remains on `127.0.0.1:8787`, the response includes provenance, and no credential-bearing fields enter the model prompt.
9. If SET is required, use only a specifically approved lab device after both global and per-device write gates are enabled. SET remains a privileged network change and is not an automatic API action.
10. Confirm service errors, status exports, API output, audit data and AI requests contain no secret values.

## Firewall boundary

Before any firewall modification, record existing rules, identify the exact trusted source network/interface, prepare rollback, avoid public exposure and limit the change to UDP/162 (and UDP/161 only if Edge1 intentionally exposes an agent). Verify connectivity and unrelated service health afterward. Port `8112` and the existing AI gateway port `8787` remain loopback-only.

## Operations Center publication

The existing publisher now installs both the main Operations Center page and the SNMP module. Run it only after the repository checkout and current static document root are confirmed:

```bash
sudo /opt/edge1-management-interface/deploy/operations-center/publish.sh
curl --fail --silent http://127.0.0.1/edge1-status/operations-center/snmp.html >/dev/null
curl --fail --silent http://127.0.0.1/edge1-status/operations-snmp.json >/dev/null
```

## Enablement

After validation:

```bash
sudo systemctl enable --now edge1-snmp-api.service
sudo systemctl enable --now edge1-snmp-poller.timer
systemctl is-active edge1-snmp-api.service
systemctl is-active edge1-snmp-poller.timer
ss -lntup | grep -E '(:8112|:8787|:161|:162)'
curl --fail --silent http://127.0.0.1:8112/api/snmp/health
```

The control API must remain loopback-only unless an existing authenticated private proxy architecture explicitly requires another path.

## Acceptance checklist

Configuration parses; repository tests pass; SNMPv3 authPriv GET/WALK succeeds; legacy protocol never appears without explicit approval; controlled SET is rejected unless both gates pass; 64-bit counter/reset/reboot behavior is correct; trap/inform handling persists; telemetry survives process restart; retention stays bounded; topology does not fabricate links; incident correlation preserves evidence confidence; model-backed AI uses only the accepted loopback BigBird gateway and sanitized evidence; action proposals remain policy bounded; audit distinguishes human/deterministic/AI involvement; systemd units recover; listeners and firewall scope are exact; secrets are absent from Git/logs/API/status exports/AI prompts; Operations Center module loads through the approved private UI; unrelated Edge1 services remain healthy.

## Rollback

Stop/disable only the new SNMP units, restore `/etc/edge1-snmp/config.json` from the timestamped evidence backup if changed, restore separately backed-up `snmptrapd` configuration, revert only the specific SNMP firewall rule if one was added, and restart only directly affected services. Republish the prior Operations Center source if the UI must be reverted. Preserve the SQLite database as operational evidence unless an explicit approved restore procedure requires replacement. Do not alter or roll back the accepted BigBird Private AI gateway as part of an SNMP rollback.
