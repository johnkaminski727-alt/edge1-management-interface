# Unified Communications — Phase 25 State Supplement

Date: 2026-08-18

This file supplements `.agent/unified-communications.md` and `.agent/unified-communications-validation-20260818.md` with the later authenticated Edge1 Phase 25 evidence. Where those earlier narrative files describe Voice/SIP operational health as `degraded`, use the current machine-readable readiness matrix and this supplement instead: current peer/interconnect operational health remains `unknown` because the analytics value came from a stale July 20 snapshot.

## Phase 25 accepted local Voice/SIP state

The Asterisk PJSIP duplicate-transport defect is repaired and accepted on `edge1.ww.cx`.

Accepted live state:

- FreePBX BMO active bind: UDP `127.0.0.1:5061`;
- generated Asterisk transport: `127.0.0.1-udp`;
- live PJSIP registry: exactly one transport object;
- custom duplicate transport file: empty;
- Kamailio retains TCP/UDP `5060`;
- Asterisk owns loopback UDP `127.0.0.1:5061` only for SIP;
- Asterisk HTTP/HTTPS reconciled to loopback `127.0.0.1:8088` and `127.0.0.1:8089`;
- zero active calls and zero active channels at final acceptance;
- adjacent telephony, Messaging and PostgreSQL services active;
- no post-restart duplicate-object or transport bind errors.

Evidence:

`/var/lib/wwcx-deployment-evidence/asterisk-pjsip-transport-repair/20260818T172956Z`

Rollback:

`/var/lib/wwcx-deployment-evidence/asterisk-pjsip-transport-repair/20260818T172956Z/rollback.sh`

Repository acceptance record:

`docs/communications/unified-communications-voice-sip-pjsip-transport-acceptance-20260818.md`

## Readiness interpretation

Do not promote end-to-end Voice/SIP peer/interconnect health from this local transport repair alone.

Preserve:

- `voice_sip.live_acceptance = runtime_ready`;
- `voice_sip.edge1_runtime = unknown` for current peer/interconnect operational health;
- production authorization blocked;
- call origination, carrier-route, trunk, dialplan, emergency-calling and provider mutations separately controlled.

The local PJSIP transport defect is no longer an unresolved Voice/SIP follow-up. Any future Voice/SIP operational-health work should focus on fresh peer/interconnect evidence without using production calls or unauthorized provider changes as a diagnostic shortcut.

## Global UC blockers unchanged

The two remaining global safe-scope blockers remain:

1. private MMS quarantine storage plus trusted scanner integration;
2. an authoritative native Mail Room correspondence/thread source for `mail.correspondence.read`.

`fresh_edge1_runtime_verified` remains `false` until those safe-scope blockers are completed or explicitly resolved.