# PBX and SMS/MMS operational observability increment — 2026-08-23

## Objective

Close safe, non-traffic operational gaps in the Edge1 PBX and Messaging surfaces without originating calls, sending SMS/MMS, changing trunks/routes/dialplan, releasing quarantine, configuring provider credentials, or exposing new public listeners.

## Fresh live basis

Read-only Edge1 operator observations at approximately 2026-08-23 05:32Z showed:

- Telephony status mode `live_read_only` and overall status `healthy`.
- Asterisk PBX process running with UDP/5060 listening.
- Zero active calls and zero currently reported registrations.
- Asterisk version 22.10.1 with PJSIP modules loaded.
- Asterisk HTTP bound to `127.0.0.1:8088` and HTTPS to `127.0.0.1:8089`.
- `wwcx-messaging-gateway.service` active and its health endpoint returning `status=ok`.
- `edge1-lab-peer` healthy in the interconnect view.
- `lab-carrier-001-peer` remains failed/pending and is not evidence of a production carrier path.

These are read-only observations. They do not authorize production telephony or messaging traffic.

## PBX correction

The prior telephony status collector derived the `registrations` metric by counting `Endpoint:` rows from `pjsip show endpoints`. Endpoints and active contacts/registrations are not the same operational fact.

The updated collector now uses a fixed allowlist of read-only Asterisk CLI commands:

- `core show channels count`
- `pjsip show endpoints`
- `pjsip show contacts`
- `pjsip show registrations`
- `pjsip show transports`

It emits aggregate counts only:

- active channels;
- active calls;
- calls processed;
- configured PJSIP endpoints;
- active PJSIP contacts;
- outbound registration objects;
- transports.

The legacy `registrations` metric is now sourced from PJSIP contacts rather than endpoint definitions. No endpoint names, SIP URIs, contact addresses, caller/callee data, credentials, SDP, headers, or media are added to the status payload.

Arbitrary Asterisk CLI input remains impossible: the helper rejects commands outside the fixed allowlist before invoking the CLI.

## SMS/MMS security telemetry

The Messaging Operations health collector now adds fixed, read-only observations for:

- `/healthz` and `/readyz` status;
- readiness storage backend;
- presence and exact `0700` posture of `/var/lib/wwcx-messaging-gateway/private-mms-quarantine` when observable by the operations identity;
- availability and bounded version output from the fixed `/usr/bin/clamscan --version` probe.

It does not enumerate quarantine objects, read attachment/message content, invoke a scan, fetch provider media, inspect credentials, or release/delete content.

Diagnostics distinguish:

- secure observable quarantine root;
- present but overly broad quarantine permissions;
- absent or unobservable quarantine state;
- scanner available/unavailable;
- combined freshly observed MMS security readiness.

The gateway service health state remains separate from MMS security readiness so an inability of the operations identity to inspect the private root does not falsely claim that the core gateway process is down. Carrier media must remain fail-closed/held whenever MMS security readiness is not freshly proven.

## Validation

Dedicated validations cover:

- fixed PBX command allowlist and rejection of arbitrary CLI commands;
- active-channel/call parsing;
- PJSIP endpoint/contact/registration/transport aggregate parsing;
- quarantine mode checks without reading content;
- fixed scanner-version probing;
- MMS security diagnostic classification;
- continued `production_actions_enabled=false` and quarantine-release denial.

## Remaining controlled work

After repository validation and merge:

1. deploy/reconcile the updated read-only status sources on Edge1 and capture fresh live acceptance;
2. capture the actual `wwcx-messaging-gateway.service` unit definition before creating a tracked repository unit, because the live invocation must not be guessed;
3. keep Telnyx and Bandwidth adapters unregistered until provider/account/DID/credential/public-webhook and live-canary gates are explicitly crossed;
4. keep PBX carrier paths unverified until provider-specific documentation or a separately authorized controlled interoperability test exists;
5. do not originate calls/messages, modify emergency routing, change trunks/dialplan, release MMS quarantine, or enable production traffic as part of this increment.
