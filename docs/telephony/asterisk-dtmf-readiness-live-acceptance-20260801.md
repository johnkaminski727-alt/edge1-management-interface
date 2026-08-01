# Asterisk DTMF Readiness Live Acceptance — 2026-08-01

## Authoritative execution record

Authenticated operator execution occurred on `edge1.ww.cx` as `wwadmin` with bounded `sudo` elevation. The repository was synchronized to clean `main` at:

```text
a600a341bdaaefde8b6bde89cfb9dba48877f500
```

The DTMF readiness implementation was present through merged PR #197, merge commit:

```text
0703b88b227b346e022a40ca931e34d0874559cd
```

Protected evidence:

```text
/var/lib/wwcx-deployment-evidence/asterisk-dtmf-readiness/20260801T073955Z
```

Primary console record:

```text
/var/lib/wwcx-deployment-evidence/asterisk-dtmf-readiness/20260801T073955Z/operator-console.txt
SHA-256: e1676f4caa8ff56caf91049080f20b41a46f654e678b64eca3c17fd628c786f4
```

Evidence manifest:

```text
/var/lib/wwcx-deployment-evidence/asterisk-dtmf-readiness/20260801T073955Z/evidence-files.sha256
SHA-256: 8424ad369ccb0f9c2a2990f3320572a44c1543ce0963e4b58fd0c71cdadd3107
```

The authenticated audit exited `0`, reported one warning and zero failures, and ended in:

```text
Audit state: READ-ONLY REVIEW COMPLETE WITH WARNINGS
```

## Accepted local-platform observations

- Asterisk `22.10.1` was running.
- System uptime and time since last reload were both approximately eight hours.
- Zero active channels, zero active calls, and zero processed calls were observed before and during the audit.
- `app_senddtmf.so`, `app_playtones.so`, `app_read.so`, the PJSIP endpoint functions, `res_pjsip_sdp_rtp.so`, `res_rtp_asterisk.so`, and DSP support were loaded.
- Runtime `SendDTMF()` help explicitly advertised `0-9`, `*`, `#`, lowercase `a-d`, and uppercase `A-D`.
- Runtime `PJSIP_DTMF_MODE()` help was present.
- The local RFC 4733 implementation was inspected and the complete DTMF event range was recorded as `0-15`.
- No configured PJSIP endpoint DTMF-policy records were found.
- No `SendDTMF()` or `PJSIP_DTMF_MODE()` references were counted in the inspected dialplan files.
- Existing FreePBX dialplan files contained ordinary input-handling references such as `Read`, `WaitExten`, and `Background`; their presence is not evidence of carrier DTMF interoperability.

## Offline complete-keypad result

The synthetic in-process generator/detector passed all sixteen symbols:

```text
1 2 3 A
4 5 6 B
7 8 9 C
* 0 # D
```

Accepted offline result:

```text
audit_state=PASS
digits_expected=123A456B789C*0#D
digits_tested=16
rfc4733_event_range=0-15
failed_digits=none
network_access=false
channel_created=false
call_originated=false
```

This confirms the repository's local signal-generation and detection logic for all sixteen DTMF frequency pairs. It does not prove behavior across SIP, RTP, SBC, carrier, gateway, codec, transcoding, or application paths.

## Warning classification

The single warning is accepted and remains open:

```text
no endpoint DTMF policy records were found; carrier path capability remains unverified
```

The warning is not a service failure. It records an evidence gap: no active endpoint or trunk policy was available to establish configured `dtmf_mode`, live SDP negotiation, SIP INFO behavior, in-band behavior, or extended `A-D` handling on an interconnect.

## Accepted capability decision

```text
local_senddtmf_application=inspected
local_rfc4733_implementation=inspected
rfc4733_event_range=0-15
standard_digits=0-9,*#
extended_digits=A-D
sip_info_policy=inventory_only
inband_policy=inventory_only
carrier_interconnect_capability=unverified
live_negotiation=not_tested
live_receive_path=not_tested
live_send_path=not_tested
call_originated=no
channel_created=no
tone_transmitted=no
```

## Change and safety verification

- Repository state was clean before and after execution.
- The repository remained at the synchronized `main` revision.
- No channel or call was created.
- No DTMF digit, RTP telephone event, SIP INFO request, in-band tone, or media was transmitted.
- No Asterisk, FreePBX, Kamailio, database, listener, route, endpoint, trunk, dialplan, module, service, firewall, package, certificate, or emergency-calling configuration changed.
- The operator reported `runtime_mutation=none`.

## Decision boundary

Accepted:

- local Asterisk DTMF send capability inspection;
- local Asterisk RFC 4733 implementation inspection;
- the `0-15` event-range capability model;
- offline validation of `0-9`, `*`, `#`, and `A-D`;
- the protected evidence and hashes above;
- continued read-only endpoint-policy reconciliation.

Not proven, authorized, or performed:

- live endpoint, trunk, carrier, SBC, or gateway interoperability;
- SDP negotiation or packet-level event-range validation;
- SIP INFO acceptance;
- in-band DTMF behavior under any codec or transcoding path;
- end-to-end receipt of ordinary or extended DTMF;
- production calls or test calls;
- emergency-calling path testing;
- carrier routing or endpoint configuration changes;
- any certification, conformance, regulatory, NPAS, EAS, or Alert Ready claim.

## Next gate

The next permitted step is a read-only reconciliation of runtime PJSIP endpoint visibility and the authoritative FreePBX/generated endpoint-policy sources. Every carrier path must remain `unverified` until provider documentation or a separately authorized controlled live test produces retained evidence.
