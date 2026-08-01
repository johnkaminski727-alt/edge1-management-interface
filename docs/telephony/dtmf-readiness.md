# Asterisk DTMF Readiness

## Purpose

This runbook establishes a read-only method to inventory Asterisk DTMF capability and endpoint policy without creating a channel, originating a call, sending a DTMF event, transmitting an in-band tone, or changing telephony configuration.

The repository slice contains:

- `tools/telephony/asterisk_dtmf_readiness_audit.sh` — authenticated read-only Edge1 audit;
- `tools/telephony/dtmf_offline_probe.py` — synthetic 16-key generator/detector probe with no network or telephony I/O;
- `config/telephony/dtmf-capability-matrix.json` — sanitized carrier/interconnect evidence template;
- `tests/validate_asterisk_dtmf_readiness_audit.py` — static and functional safety validation.

## Capability model

The complete DTMF keypad contains sixteen symbols:

```text
1 2 3 A
4 5 6 B
7 8 9 C
* 0 # D
```

RFC 4733 assigns events `0-9` to the numeric digits, event `10` to `*`, event `11` to `#`, and events `12-15` to `A-D`. A normal SDP capability for the complete keypad is represented by `telephone-event` with event range `0-15`.

Asterisk PJSIP endpoint policy supports these `dtmf_mode` values:

- `rfc4733` — named RTP telephone events outside the main audio waveform;
- `inband` — DTMF carried as audio;
- `info` — DTMF carried in SIP INFO requests;
- `auto` — RFC 4733 when negotiated, otherwise in-band;
- `auto_info` — RFC 4733 when negotiated, otherwise SIP INFO.

An absent endpoint `dtmf_mode` is recorded by this audit as `implicit-rfc4733`, reflecting the documented Asterisk default. This describes configuration intent only. It does not prove negotiation or carrier behavior.

## Safety boundary

**No channel, call, tone transmission, SIP request, or production telephony change is performed by this audit.**

The audit may:

- inspect Asterisk version, uptime, channel counts, module inventory, and CLI help;
- parse only whitelisted, non-secret PJSIP endpoint fields;
- count DTMF-related dialplan application references without copying dialplan content;
- hash and record metadata for inspected configuration files;
- generate and detect synthetic tones in process memory;
- write protected evidence below `/var/lib/wwcx-deployment-evidence/asterisk-dtmf-readiness/`.

The audit must not:

- run `channel originate`, `originate`, `Dial`, `SendDTMF`, ARI send-DTMF, AMI Originate, or an equivalent live action;
- create a channel or call;
- send RTP telephone events, SIP INFO requests, or in-band audio;
- reload or restart Asterisk, FreePBX, Kamailio, RTP services, or any carrier component;
- change endpoint, trunk, transport, dialplan, codec, route, firewall, certificate, package, or emergency-calling configuration;
- expose endpoint names, telephone numbers, SIP URIs, credentials, authentication data, or customer records;
- claim carrier interoperability, emergency-path readiness, or certification from offline evidence.

## Repository validation

From the repository root:

```bash
python3 tests/validate_asterisk_dtmf_readiness_audit.py
```

The validator checks shell syntax, the offline 16-key probe, the JSON matrix, the command allowlist, the evidence boundary, and the absence of call-origination or telephony mutation behavior.

The offline probe can also be run directly:

```bash
python3 tools/telephony/dtmf_offline_probe.py
python3 tools/telephony/dtmf_offline_probe.py --json
```

A passing probe confirms only that the repository generator/detector correctly distinguishes all sixteen DTMF frequency pairs at the configured sample rate and duration.

## Edge1 read-only audit

Use a clean, synchronized `main` checkout. The script itself performs no service or configuration mutation.

```bash
cd /opt/edge1-management-interface
set -Eeuo pipefail
umask 077

test "$(hostname -f)" = "edge1.ww.cx"
test -z "$(git status --porcelain)"

TS=$(date -u +%Y%m%dT%H%M%SZ)
EVID="/var/lib/wwcx-deployment-evidence/asterisk-dtmf-readiness/$TS"

sudo sh tools/telephony/asterisk_dtmf_readiness_audit.sh \
  --expected-host edge1.ww.cx \
  --evidence-dir "$EVID" 2>&1 | \
  sudo tee "$EVID/operator-console.txt"

RC=${PIPESTATUS[0]}
sudo sha256sum "$EVID/operator-console.txt" | \
  sudo tee "$EVID/operator-console.txt.sha256"

printf 'audit_exit_code=%s\n' "$RC"
printf 'evidence=%s\n' "$EVID"
exit "$RC"
```

The expected terminal state is either:

- `Audit state: READ-ONLY REVIEW COMPLETE`; or
- `Audit state: READ-ONLY REVIEW COMPLETE WITH WARNINGS` when endpoint or carrier evidence remains incomplete.

A warning is not permission to alter production configuration. Review the evidence first.

## Evidence interpretation

### Strong local evidence

The following can be established without a call:

- relevant Asterisk modules are loaded;
- Asterisk CLI documents standard and extended `SendDTMF` symbols;
- PJSIP endpoint DTMF modes are syntactically recognized;
- DTMF-related dialplan applications are present or absent by count;
- all sixteen frequency pairs pass the offline probe;
- no active call details, signaling content, or media are captured.

### Evidence that remains unavailable without a controlled path test

The audit cannot prove:

- which DTMF modes a carrier actually accepts;
- the event range negotiated in real SDP;
- whether `A-D` survives each endpoint, SBC, carrier, gateway, or application path;
- whether SIP INFO is accepted or rejected by a peer;
- whether in-band tones survive codec selection, transcoding, packet loss, echo control, or media bypass;
- end-to-end detection timing, duplicate suppression, duration handling, or packet-loss tolerance;
- emergency-calling or production-route behavior.

## Carrier capability matrix

Populate `config/telephony/dtmf-capability-matrix.json` only with sanitized internal identifiers and one of these evidence states:

- `unknown` — no reliable evidence;
- `documented` — provider documentation explicitly supports the mode or range;
- `controlled-test-passed` — a separately authorized test produced retained evidence;
- `controlled-test-failed` — a separately authorized test failed with retained evidence.

Do not infer `A-D` support merely because a provider supports ordinary `0-9`, `*`, and `#`. Do not record credentials, telephone numbers, SIP URIs, customer identifiers, or raw signaling payloads in the matrix.

## Controlled live test gate

A live test is a separate production-traffic action. It requires explicit authorization for:

1. the exact test endpoint and route;
2. the permitted digits and direction;
3. the test window and responsible operator;
4. confirmation that the route is not an emergency-calling path;
5. capture and retention rules for sanitized signaling evidence;
6. rollback or stop conditions;
7. confirmation that no customer or third-party destination will be contacted unexpectedly.

Until that authority exists, the correct result for carrier paths is `unverified`.

## Authoritative references

- RFC 4733, *RTP Payload for DTMF Digits, Telephony Tones, and Telephony Signals*.
- Asterisk 22 `SendDTMF()` application documentation.
- Asterisk `res_pjsip` endpoint `dtmf_mode` documentation.
- Asterisk `PJSIP_DTMF_MODE()` and `PJSIP_ENDPOINT()` function documentation.
