# Unified Communications — Voice/SIP Read-Only Live Acceptance

Date: 2026-08-18
Host: `edge1.ww.cx`
Scope: fresh bounded read-only Voice/SIP functional acceptance

## Result

Phase 19 passed the repository-provided telephony analytics live acceptance audit and the surrounding operator-run read-only checks. This establishes fresh functional acceptance for the bounded Voice/SIP read/status surface. It does not assert current live interconnect health and does not authorize production traffic or mutations.

Evidence directory:

`/var/lib/wwcx-deployment-evidence/telephony-analytics-live-acceptance/uc-phase19-20260818T112551Z`

## Accepted runtime facts

- Asterisk, Kamailio, `wwcx-telephony-analytics.service`, and `wwcx-telephony-console.service` were active before and after the audit.
- The live repository telephony assets matched current `origin/main` at `7ca3b8360de740d844edcb8c598b1988407a16e5` for the audited files.
- The repository-provided audit reported zero warnings and zero failures.
- Runtime `telephony_analytics_api.py` and `telephony_platform.py` source hashes matched the canonical repository sources.
- The analytics service ran as `wwadmin:wwadmin` with the expected hardened systemd properties.
- The analytics listener remained loopback-only at `127.0.0.1:8099`.
- Health, calls-summary, and interconnect-summary endpoints returned valid aggregate payloads.
- Payload validation, privacy scanning, and anomaly-contract validation all passed.
- POST to the read-only health endpoint returned HTTP 405.
- Asterisk reported version 22.10.1, zero active calls, and zero calls processed at the acceptance point.
- The audit recorded `database_query_performed=no`, `credentials_read=no`, `customer_identifiers_retained=no`, `call_origination_performed=no`, `dtmf_transmission_performed=no`, `carrier_route_changed=no`, `service_mutation=none`, and `runtime_mutation=none`.
- Messaging PostgreSQL, Communications workspace, Relay, and BigBird remained active alongside the telephony services.
- Post-audit available memory remained approximately 1.5 GiB; the existing 1 GiB swap remained almost fully consumed.

## Health-source qualification

The Phase 19 API response reported:

- `overall_status: critical`;
- platform health score `28`;
- component `sip: degraded`;
- `interconnects_total: 2`;
- `attention_required: 1`;
- interconnect states: one healthy and one failed.

Those values must not be interpreted as a fresh live carrier/interconnect probe. Source inspection after Phase 19 confirmed that `server/telephony_analytics_api.py` builds the SIP/interconnect summary from repository file `data/registry/interconnect/status/peer-status.json`. The current repository snapshot records `last_check: 2026-07-20T10:41:47.461529Z`; it marks `edge1-lab-peer` healthy and `lab-carrier-001-peer` failed with a name-resolution error (`[Errno -2] Name or service not known`). The API therefore surfaced a stored lab-status snapshot rather than performing a current network or SIP OPTIONS probe.

Accordingly, the readiness matrix distinguishes functional acceptance from operational-health freshness:

- `voice_sip.live_acceptance = runtime_ready` for the bounded read-only functional surface;
- `voice_sip.edge1_runtime = unknown` because Phase 19 did not establish fresh live interconnect operational health.

The stored failed lab-peer status remains useful diagnostic data, but it is not sufficient evidence of a current production interconnect failure or current SIP degradation.

## Safety boundary

No calls were originated. No DTMF was transmitted. No route, trunk, dialplan, emergency-calling, or carrier configuration was changed. No telephony service was restarted. No telephony database was mutated. No credentials were read or displayed. No synthetic customer call records were created.

## Readiness effect

Fresh Voice/SIP read-only acceptance is no longer a missing global safe-scope acceptance item. The global `fresh_edge1_runtime_verified` flag remains false because MMS private quarantine storage/trusted scanning and authoritative Mail correspondence remain incomplete. Current live Voice/SIP operational health remains unknown until a separately approved fresh read-only health source or probe is available; no production traffic or route/carrier mutation should be used merely to force that determination.
