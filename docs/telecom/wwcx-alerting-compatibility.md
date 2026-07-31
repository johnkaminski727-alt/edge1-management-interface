# WW.CX EBS and CAP-CP Compatibility Foundation

**Status:** repository-staged, receive-side and test-only  
**Production alert origination:** prohibited  
**Public distribution:** not implemented  
**Last reviewed:** 2026-07-31

## Objective

Provide a bounded compatibility foundation for receiving and validating OASIS CAP 1.2 messages that identify the Canadian CAP-CP profile, and for recognizing the retired U.S. Emergency Broadcast System 853/960 Hz attention signal in recorded PCM audio.

Compatibility is not certification. This foundation does not make WW.CX, CreekCo, Asterisk, or Edge1 an authorized Alert Ready, NPAS, EAS, or emergency-alert origination system.

## Implemented components

`tools/alerting/capcp_probe.py` validates a bounded local XML file, blocks DTD/entity declarations, requires the CAP 1.2 namespace and CAP-CP markers, checks required fields, multilingual event consistency and location targeting, rejects `Actual` alerts by default, and emits sanitized JSON. It performs no network access and has no transmission path.

`tools/alerting/ebs_tone_probe.py` accepts a bounded uncompressed 16-bit PCM WAV file and detects simultaneous energy near 853 Hz and 960 Hz. It never generates, plays, routes, or transmits an attention signal.

## Safe architecture

```text
Authorized CAP-CP source (not configured)
        |
        v
Quarantined local ingress
        |
        v
CAP 1.2 + CAP-CP validation
        |
        v
Normalized internal alert record
        |
        v
Human/policy approval gate
        |
        +--> read-only display
        +--> isolated audio-rendering test
        +--> future Asterisk adapter, disabled until separately authorized
```

Asterisk must remain a delivery adapter, not the trust authority. It must never accept arbitrary public XML and immediately originate calls or pages.

## Required gates before live delivery

- written authority to consume the selected CAP-CP feed;
- documented endpoint, trust anchors, authentication and redistribution terms;
- complete normative CAP 1.2 schema and CAP-CP rule-set validation;
- managed event/location reference validation;
- signature and issuer trust policy where required;
- replay, duplicate, update, cancel, expiry and clock-skew controls;
- bilingual rendering and accessibility review;
- geographic targeting and Test/Exercise/Actual separation;
- protected activation control;
- audit, retention, rollback and incident procedures;
- formal conformance and governance review before any public claim.

## Validation

```bash
python3 -m py_compile tools/alerting/capcp_probe.py tools/alerting/ebs_tone_probe.py
python3 -m unittest tests/test_alerting_compatibility.py
python3 tools/alerting/capcp_probe.py tests/fixtures/alerting/capcp-test-alert.xml
```

The fixture is synthetic, `Test`, `Restricted`, and uses the reserved `.invalid` domain.

## Asterisk boundary

The current Edge1 Asterisk instance has the audio and dialplan primitives needed for a future controlled adapter, but no CAP-CP alert context, authorized endpoint, protected activation workflow or public-delivery authority exists. Do not add an inbound public route, automatic call origination, paging group or carrier path as part of this foundation.
