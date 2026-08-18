# WW.CX Unified Communications — Phase 25 Handoff Supplement

Date: 2026-08-18

This handoff supplements `docs/handoff/unified-communications-completion-20260818.md` with later authenticated Edge1 evidence.

## Voice/SIP local transport repair

Phase 25 repaired the Asterisk PJSIP transport source-of-truth on `edge1.ww.cx`.

Final accepted local runtime:

- FreePBX active PJSIP UDP bind: `127.0.0.1:5061`;
- generated transport id: `127.0.0.1-udp`;
- live PJSIP registry: one transport object;
- duplicate custom transport retired;
- Kamailio retains TCP/UDP `5060`;
- Asterisk SIP remains loopback-only on UDP `127.0.0.1:5061`;
- Asterisk HTTP/HTTPS are loopback-only on `127.0.0.1:8088` and `127.0.0.1:8089` after restart reconciled runtime to generated FreePBX configuration;
- zero active calls/channels;
- no post-restart transport bind errors;
- no production SIP probe or call generated.

Evidence:

`/var/lib/wwcx-deployment-evidence/asterisk-pjsip-transport-repair/20260818T172956Z`

Rollback:

`/var/lib/wwcx-deployment-evidence/asterisk-pjsip-transport-repair/20260818T172956Z/rollback.sh`

Detailed repository acceptance:

`docs/communications/unified-communications-voice-sip-pjsip-transport-acceptance-20260818.md`

## Superseded narrative

The earlier completion handoff described Voice/SIP operational health as degraded/critical. That language should not be used as a current live-health claim. The current readiness matrix correctly records `voice_sip.edge1_runtime = unknown` because the analytics degradation was derived from a stale July 20 repository snapshot rather than a fresh live peer probe.

Phase 25 proves the local Asterisk transport runtime is healthy; it does not prove current carrier/interconnect health.

Preserve:

- `voice_sip.live_acceptance = runtime_ready`;
- `voice_sip.edge1_runtime = unknown` for current peer/interconnect health;
- production authorization blocked.

## Remaining global safe-scope blockers

Unchanged:

1. MMS private quarantine storage and trusted scanner integration;
2. authoritative native Mail Room correspondence/thread source for `mail.correspondence.read`.

Do not use live calls, carrier traffic, emergency-routing changes, trunk/dialplan changes, or provider mutations to close the remaining Voice/SIP evidence gap without separate authorization.