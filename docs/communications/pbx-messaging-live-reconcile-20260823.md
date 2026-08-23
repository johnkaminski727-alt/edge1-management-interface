# PBX + Messaging live observability reconciliation — 2026-08-23

## Purpose

Provide one authorization-gated operator action that deploys the reviewed read-only Telephony Console model and captures fresh PBX/SMS/MMS runtime evidence without touching Asterisk routing, the Messaging Gateway process, carrier traffic, credentials, quarantine content, or public infrastructure.

## Mutation scope

The apply wrapper may restart **only** `wwcx-telephony-console.service`, which serves the loopback read-only Telephony Operations UI/API from repository source.

It explicitly records the pre/post `MainPID` for:

- `asterisk.service`;
- `wwcx-messaging-gateway.service`;
- `wwcx-telephony-console.service`.

Acceptance requires Asterisk and Messaging Gateway PIDs to be unchanged. Any unexpected Asterisk or Messaging process restart fails the operation.

The wrapper does not restart/reload Asterisk or Messaging Gateway, alter a trunk/route/dialplan, originate a call, send SMS/MMS, release quarantine, configure a carrier, or alter DNS/firewall/certificates/authentication.

## Preflight

The wrapper requires:

- host `edge1.ww.cx`;
- root execution;
- clean repository checkout on `main`;
- exact reviewed 40-character commit supplied by the operator;
- all three services active before the change;
- installed Telephony Console unit still pointing at `/opt/edge1-management-interface/server/telephony_status_server.py` on `127.0.0.1:8096`;
- TCP/8096 actually present and loopback-only;
- focused PBX, planned-peer, Messaging/MMS and console validations passing before restart.

## Acceptance

After the Telephony Console restart, the wrapper requires:

- `/healthz` to recover on `127.0.0.1:8096`;
- live status mode `live_read_only`;
- the current registry to report one configured health-check-applicable trunk, one healthy configured trunk, and one planned peer;
- `lab-carrier-001-peer` to report `planned` with `health_check_applicable=false`;
- Asterisk and Messaging Gateway to remain active with unchanged PIDs;
- TCP/8096 to remain loopback-only;
- fresh secret-free Messaging/MMS observability output;
- a redacted runtime capture package with unit metadata, aggregate Asterisk/PJSIP counts, Messaging health/readiness, quarantine-root metadata and ClamAV version.

## Console rollback

If any gated check after restart fails, the wrapper temporarily restores the Telephony Console source from the parent commit, restarts only the Telephony Console to recover the previous runtime behavior, then restores the reviewed source on disk so the repository remains on the reviewed commit. It records `rollback_performed=true`.

No Asterisk or Messaging Gateway rollback action is needed because neither process is intentionally changed.

## Evidence

Successful runs are written under:

`/var/lib/wwcx-deployment-evidence/pbx-messaging-observability/<UTC timestamp>/`

Evidence is root-private and SHA-256 indexed. It excludes message bodies, telephone numbers, SIP URIs, endpoint names, credentials, environment values, quarantine contents and media.
