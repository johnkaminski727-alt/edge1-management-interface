# Unified Communications — PBX + SMS/MMS continuation

Date: 2026-08-23

## Mission

Advance the remaining safe PBX and SMS/MMS operational work without production calls/messages, route or dialplan mutation, carrier activation, emergency-calling changes, quarantine release, credentials, DNS/firewall/certificate changes, or public-listener changes.

## Fresh live observations

Read-only operator evidence at approximately 05:32Z:

- Asterisk PBX healthy; process running; UDP/5060 listening.
- Asterisk 22.10.1; PJSIP stack loaded.
- zero active calls and zero currently reported registrations.
- Asterisk HTTP/HTTPS remain loopback-only on 8088/8089.
- WW.CX Messaging Gateway healthy.
- one synthetic/local interconnect healthy; `lab-carrier-001-peer` remains failed/pending.

## Repository increment in progress

Branch: `agent/pbx-sms-mms-observability-20260823`
Base: `b906bcb2b874d8bb86226d3cdf43d895c7663bc2`

Changes:

- replace endpoint-count-as-registration inference with fixed read-only aggregate Asterisk/PJSIP collection;
- expose active channels/calls, endpoints, contacts, outbound registration objects and transports without identities;
- reject arbitrary Asterisk CLI commands before execution;
- add read-only Messaging readiness storage, private MMS quarantine-mode and fixed ClamAV version observations;
- add diagnostics for fresh MMS security posture while preserving gateway health as a separate fact;
- keep quarantine release and all production messaging actions disabled;
- add focused validation and operator documentation.

## Known remaining blockers / future gates

- Live Messaging systemd unit still needs exact definition capture before repository tracking; do not invent `ExecStart` or environment paths.
- Telnyx and Bandwidth source adapters remain unregistered for production.
- Real carrier credentials/DID/public webhook/live canaries remain separate explicit approval gates.
- PBX carrier interoperability remains unverified; do not originate calls merely to improve displayed health.
- MMS clean/malicious scanner acceptance was previously achieved, but this increment aims to make the runtime posture visible/fresh without exposing private content.

## Safety invariant

Read/observe/validate only. No live call or message traffic, quarantine release, trunk/route/dialplan mutation, carrier action, number porting, emergency-calling test, STIR/SHAKEN signing, credential operation, or public infrastructure change.
