# Edge1 SNMP + AI Operations Platform

## Architecture

The platform follows the existing Edge1 private-first pattern and keeps SNMP management inside the WW.CX Operations Center rather than introducing a parallel admin product.

- `server/edge1_snmp_platform.py` provides inventory, SQLite persistence, bounded discovery validation, Net-SNMP polling, trap normalization, deterministic anomaly math, evidence queries, action policy and audit records.
- `server/edge1_snmp_api.py` exposes a loopback-only HMAC-authenticated API on proposed local port `8112`.
- Net-SNMP command-line tools perform protocol operations. New device profiles default to SNMPv3 `authPriv`; v1/v2c onboarding requires explicit legacy approval.
- Net-SNMP `snmptrapd` should own UDP/162 and invoke `tools/edge1_snmp_trap_ingest.py`. The repository does not claim or configure a public listener.
- SQLite separates inventory/configuration, telemetry, events, alerts, MIB metadata, action proposals and audit records.
- `src/web/operations-center/snmp.html` is an Operations Center module using the existing static private UI convention.

## Credential model

Inventory stores only `credential_reference`. Secret profiles live outside Git under `/etc/edge1-snmp/profiles/<reference>.json`, must be mode 0600 or stricter, and are loaded only at execution time. The poller does not log command arguments. API output never contains secret values. The API signing secret is external to Git at `/etc/edge1-snmp/api.secret`.

A profile is shaped like this, with real values supplied only on Edge1:

```json
{"version":"3","username":"<provisioned-user>","auth_protocol":"SHA","auth_password":"<secret>","priv_protocol":"AES","priv_password":"<secret>"}
```

Do not copy real profiles into the repository, documentation, AI prompts or evidence packages.

## Deterministic analytics and AI boundary

Raw numerical work remains deterministic. `counter_rate()` handles normal increments, 32/64-bit wrap, resets and reboot suppression; `rolling_anomaly()` uses statistical baselines. `evidence_query()` produces a provider-neutral evidence envelope distinguishing observations, derived metrics, deterministic results, AI inferences, recommendations and executed actions. A future local/private model can consume this sanitized envelope without receiving credentials.

The AI layer never runs arbitrary shell commands. It creates action proposals. A deterministic policy classifies actions and only allows read-only/reversible classes to reach approved state when validation and rollback metadata are present. Privileged network changes such as SNMP SET remain review-gated.

## MIB strategy

The database includes an indexed `mib_objects` knowledge store for OID/name/module/syntax/access/status/units/description/enums. Production import should use installed Net-SNMP tooling and local MIB files; import failures must not crash polling. No WW.CX IANA Private Enterprise Number is claimed by this implementation.

## Discovery

Discovery is preview-first and bounded. A CIDR must be a subnet of a configured allowlist. Public/global ranges are rejected unless explicitly enabled, and host counts are capped. Narrow the example RFC1918 ranges to the actual trusted Edge1 management networks after authenticated inspection.

## Trap and inform handling

Use mature `snmptrapd` for the UDP listener and SNMPv3 authentication. The provided template contains no credentials, bind address or firewall scope; those values must come from authenticated Edge1 inspection. Normalized events preserve source, SNMP version, enterprise/trap OID, varbinds, severity, correlation ID and safe metadata, with duplicate suppression.

## API

The API is loopback-only by default. Except for `/api/snmp/health`, requests use the WW.CX HMAC actor/nonce/timestamp/signature convention. Current resources are documented in `src/api/snmp_contract.json`.

## Repository validation

```bash
PYTHONPATH=server python3 tests/validate_snmp_platform.py
python3 -m py_compile server/edge1_snmp_platform.py server/edge1_snmp_api.py tools/edge1_snmp_trap_ingest.py
python3 -m json.tool config/edge1-snmp.json.example >/dev/null
python3 -m json.tool src/api/snmp_contract.json >/dev/null
```

Production acceptance additionally requires a fresh authenticated Edge1 preflight, Net-SNMP availability check, trusted-interface discovery, controlled SNMPv3 polling, test trap/inform delivery, systemd validation, listener/firewall verification, security review and unrelated-service health checks.
