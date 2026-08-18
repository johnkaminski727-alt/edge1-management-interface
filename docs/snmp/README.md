# Edge1 SNMP + AI Operations Platform

## Architecture

The platform follows the existing Edge1 private-first pattern and keeps SNMP management inside the WW.CX Operations Center rather than introducing a parallel admin product.

- `server/edge1_snmp_platform.py` provides canonical inventory, SQLite persistence, base polling, trap normalization, deterministic anomaly math, evidence queries, action policy and audit records.
- `server/edge1_snmp_services.py` adds interface polling, bounded discovery, MIB import/search, alerting, topology, search and retention.
- `server/edge1_snmp_cycle.py` runs a bounded polling/interface/alert/retention cycle.
- `server/edge1_snmp_incidents.py` correlates recent failures, events and evidence-labelled topology without fabricating links.
- `server/edge1_snmp_ai.py` reuses the accepted BigBird Private AI gateway at `127.0.0.1:8787/v1/chat` for interpretation of sanitized evidence only.
- `server/edge1_snmp_api.py` exposes a loopback-only HMAC-authenticated API on proposed local port `8112`.
- `server/operations_snmp_exporter.py` publishes sanitized read-only status to the existing Operations Center status tree.
- Net-SNMP command-line tools perform protocol operations. New device profiles default to SNMPv3 `authPriv`; v1/v2c onboarding requires explicit legacy approval.
- Net-SNMP `snmptrapd` should own UDP/162 and invoke `tools/edge1_snmp_trap_ingest.py`. The repository does not claim or configure a public listener.
- SQLite separates inventory/configuration, interfaces, telemetry, events, alerts, MIB metadata/imports, topology, action proposals and audit records.
- `src/web/operations-center/snmp.html` is published with the existing Operations Center deployment path and consumes only the sanitized status export.

## Credential model

Inventory stores only `credential_reference`. Secret profiles live outside Git under `/etc/edge1-snmp/profiles/<reference>.json`, must be mode 0600 or stricter, and are loaded only at execution time. The poller does not log command arguments. API output never contains secret values. The API signing secret is external to Git at `/etc/edge1-snmp/api.secret`.

A profile is shaped like this, with real values supplied only on Edge1:

```json
{"version":"3","username":"<provisioned-user>","auth_protocol":"SHA","auth_password":"<secret>","priv_protocol":"AES","priv_password":"<secret>"}
```

Do not copy real profiles into the repository, documentation, AI prompts or evidence packages.

## SNMP operations

The platform supports GET through the standard poller and GET/WALK/GETBULK through the Net-SNMP execution boundary. `server/edge1_snmp_set.py` implements SNMP SET only after both the global `snmp_set_enabled` gate and the per-device `write_enabled` gate pass, and only with an SNMPv3 profile. SET is deliberately not exposed as an automatic API endpoint; it remains a `PRIVILEGED_NETWORK_CHANGE` policy class.

Interface polling prefers IF-MIB high-capacity (`ifHC*`) counters where available and retains legacy counters for compatibility. `counter_rate()` handles normal increments, 32/64-bit rollover, reset and reboot suppression so a restart is not treated as a bandwidth spike.

## Deterministic analytics, incident correlation and AI boundary

Raw numerical work remains deterministic. `rolling_anomaly()` uses statistical baselines. `evidence_query()` emits an evidence envelope distinguishing observed facts, derived metrics, deterministic rule results, AI inference, recommendations and executed actions. `edge1_snmp_incidents.py` correlates device failures, traps and topology; confirmed and inferred links remain visibly distinct.

The BigBird adapter signs requests using the existing `BB_RELAY_KEY_ID` / `BB_RELAY_SECRET` contract and refuses any gateway URL other than `http://127.0.0.1:8787/v1/chat`. It defensively removes secret-bearing field names before prompt construction, caps evidence size, disables unrelated communications/library/telephony contexts, and asks the model to interpret rather than calculate raw metrics. If the gateway identity is not available, the API returns deterministic evidence with a provider-unavailable error rather than pretending AI analysis occurred.

The AI layer never runs arbitrary shell commands. It creates action proposals. A deterministic policy classifies actions and only allows read-only/reversible classes to reach approved state when validation and rollback metadata are present.

## MIB strategy

The database includes an indexed `mib_objects` knowledge store for OID/name/module/syntax/access/status/units/description/enums. The operator CLI supports `oid lookup`, `oid describe`, `oid search`, `mib list`, `mib import` and `mib validate`. Production import uses installed Net-SNMP tooling and local MIB files; import failures are recorded and do not crash polling. No WW.CX IANA Private Enterprise Number is claimed by this implementation.

## Discovery

Discovery is preview-first and bounded. A CIDR must be a subnet of a configured allowlist. Public/global ranges are rejected unless explicitly enabled, host counts are capped, and the execution path uses a named credential reference rather than embedding credentials in scan definitions. Narrow the example RFC1918 ranges to the actual trusted Edge1 management networks after authenticated inspection.

## Trap and inform handling

Use mature `snmptrapd` for the UDP listener, SNMPv3 authentication and inform acknowledgement behavior. The provided template contains no credentials, bind address or firewall scope; those values must come from authenticated Edge1 inspection. Normalized events preserve source, SNMP version, enterprise/trap OID, varbinds, severity, correlation ID and safe metadata, with duplicate suppression.

## Operations Center

`server/operations_snmp_exporter.py` atomically writes `/var/www/edge1-status/operations-snmp.json`. The SNMP page is published at `/edge1-status/operations-center/snmp.html` by the existing `deploy/operations-center/publish.sh` path and reads `../operations-snmp.json`. The export intentionally omits credential references and secret material.

## API and CLI

The API is loopback-only by default. Except for `/api/snmp/health`, requests use the WW.CX HMAC actor/nonce/timestamp/signature convention. Current resources are documented in `src/api/snmp_contract.json`. `server/edge1_snmp_cli.py` provides operator-safe MIB, discovery, inventory, alert, topology and search commands.

## Repository validation

```bash
PYTHONPATH=server python3 tests/validate_snmp_platform.py
PYTHONPATH=server python3 tests/validate_snmp_services.py
PYTHONPATH=server python3 tests/validate_snmp_incidents_and_set.py
PYTHONPATH=server python3 tests/validate_snmp_ai_provider.py
python3 -m compileall -q server tests tools
python3 -m json.tool config/edge1-snmp.json.example >/dev/null
python3 -m json.tool src/api/snmp_contract.json >/dev/null
bash -n deploy/operations-center/publish.sh
```

Production acceptance additionally requires a fresh authenticated Edge1 preflight, current checkout/database/monitoring-stack reconciliation, Net-SNMP availability check, trusted-interface discovery, controlled SNMPv3 polling, SET gate validation on a specifically writable lab target if applicable, test trap/inform delivery, BigBird loopback AI query, systemd validation, listener/firewall verification, security review, Operations Center publication and unrelated-service health checks.
