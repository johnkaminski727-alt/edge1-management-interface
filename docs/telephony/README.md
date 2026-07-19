# Big Bird Telephony Operations

## Status

Phase 1 is a read-only, fixture-backed operational console for SIP, PBX, SMS/MMS, media, numbering, and carrier interconnect visibility. It deliberately exposes no production-changing controls.

## Preview

From the repository root:

```bash
python3 -m http.server 8088 --directory src/web
```

Open `http://127.0.0.1:8088/telephony/` through an approved local or private connection.

## Current surfaces

- overall network posture and summary metrics
- PBX, SIP edge, messaging, media relay, numbering, and carrier service health
- carrier and trunk OPTIONS-style health summaries
- SIP endpoint registration posture
- active alert feed
- responsive desktop and mobile layouts
- sanitized offline fixture fallback

## Adapter boundary

Production collectors must emit the normalized snapshot described by `src/api/telephony_status_contract.json`. Planned read-only adapters include Asterisk AMI/ARI, FreeSWITCH ESL, Kamailio/OpenSIPS RPC or database views, RTPengine statistics, messaging-gateway queues, numbering inventory, and controlled SIP OPTIONS probes.

Adapters must not expose credentials, message bodies, audio payloads, authentication secrets, or unredacted customer records. Public repository fixtures must remain synthetic.

## Safety model

Phase 1 is read-only. Future configuration changes must use the existing staged workflow:

```text
propose -> inspect -> validate -> approve/reject -> operator-controlled apply -> verify/rollback
```

The browser must never connect directly to PBX, carrier, or gateway administrative interfaces. A localhost-only API wrapper will normalize and redact approved data sources.

## Next implementation slice

1. localhost-only `telephony_status_server.py`
2. collector interface and fixture/live mode selection
3. SIP OPTIONS and service-process collectors
4. Asterisk registration/channel adapter
5. messaging queue adapter
6. validation, smoke tests, audit events, and deployment unit
