# Private AI Telephony Live Acceptance — 2026-08-17

- Private AI gateway version: `0.3.3-alpha.1`.
- Added independently scoped, read-only `telephony.read`.
- Added opt-in `include_telephony` chat context.
- Sources remain loopback-only on ports `8096` and `8099`.
- Context includes sanitized console status, platform health, call summaries, interconnect summaries and anomaly indicators.
- Telephony POST remained blocked with HTTP 405.
- Documentation RAG remained healthy.
- Asterisk and FreePBX remained active and were not reconfigured.
- No endpoint, trunk, registration, dialplan, route, call, DTMF, credential, database, listener, firewall, DNS, certificate or public-exposure change occurred.
- Runtime backup: `/var/backups/bigbird-ai-gateway-telephony-20260817T035035Z`.

Remaining work: signed internal-viewer chat acceptance, source-controlled gateway regression tests, News/IRC client AI controls, and guarded Asterisk/FreePBX lifecycle and transport remediation.
