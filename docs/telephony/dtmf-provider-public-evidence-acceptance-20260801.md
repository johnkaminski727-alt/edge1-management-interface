# DTMF Provider-Public Evidence Acceptance — 2026-08-01

## Scope

This record accepts the first privacy-minimized provider-public DTMF capability entry for the WW.CX telephony operations platform.

Accepted repository merge:

```text
31fb4865f409bcf474ffd3d2c61a1727161cbe4c
```

Pull request:

```text
#223 — Record partial provider DTMF capability evidence
```

This acceptance concerns repository evidence and matrix state only. It does not activate, configure, test, or certify a carrier route.

## Source basis

Current provider-public documentation states that an account-level automatic DTMF setting uses a named RTP-event mode and falls back to in-band when the far end does not support that mode. Separate public setup documentation describes a provider-hosted DTMF diagnostic destination.

The source material does not state:

- an RFC 4733 `telephone-event` event range;
- support for events `12-15` or extended keys `A-D`;
- SIP INFO support;
- codec or transcoding constraints for in-band DTMF;
- exact inbound, outbound, product, regional, SBC, or media-relay applicability;
- production-route or end-to-end interoperability results.

The repository therefore does not translate the provider's legacy RTP-event terminology into an RFC 4733 capability claim.

## Accepted repository assets

```text
config/telephony/dtmf-provider-evidence/provider-candidate-001-public-documentation.json
config/telephony/dtmf-capability-matrix.json
docs/telephony/dtmf-provider-evidence-intake.md
tests/test_validate_dtmf_provider_evidence.py
tests/validate_asterisk_dtmf_readiness_audit.py
```

The provider and route use sanitized internal identifiers only. The record contains no provider name, customer or account identifier, email address, telephone number, SIP URI, private endpoint, credential, secret, personal identifier, or private correspondence content.

## Accepted capability state

For the sanitized provider and route candidate:

```text
inband.status=documented
inband.codec_constraints=[]
rfc4733.status=unknown
rfc4733.event_range=unknown
sip_info.status=unknown
extended_abcd.status=unknown
carrier_interoperability=partially-documented
live_test_authorized=false
```

`inband.status=documented` means only that public provider account-setting documentation describes an automatic fallback to in-band. It does not prove that in-band DTMF survives any particular codec, transcoder, SBC, media relay, endpoint, trunk, direction, or production route.

## Evidence gate

The repository-wide DTMF readiness validator now permits a matrix entry only when:

- a matching sanitized provider-evidence record exists;
- that record passes the privacy-safe provider validator;
- the evidence record explicitly marks the entry matrix-eligible;
- every matrix capability state matches the evidence record exactly;
- each non-unknown capability references retained evidence;
- every unknown capability remains reference-free;
- documented RFC 4733 support includes a non-unknown event range;
- in-band codec constraints match the evidence record;
- no evidence record authorizes a live test;
- the set of matrix entries exactly matches the set of eligible evidence records.

This replaces the earlier temporary rule that required the public matrix to remain empty while preserving the underlying prohibition against unsupported carrier claims.

## Validation

The accepted branch passed:

- Edge1 Operator Validation;
- all repository Python validations;
- JSON, shell, and JavaScript validation;
- Python 3.6 shared-collector compatibility validation;
- privacy and sensitive-number regression checks;
- cross-record matrix/evidence-reference checks;
- the offline Asterisk DTMF readiness validation.

## Operational boundary

No call or channel was originated. No DTMF event, SIP INFO request, or in-band tone was transmitted. No trunk, endpoint, route, DID, dialplan, carrier account, credential, DNS record, firewall rule, certificate, service, listener, emergency-calling path, or production traffic was changed.

The correct operational conclusion remains:

- one account-level in-band fallback is provider-documented;
- carrier and end-to-end interoperability remain unverified;
- a controlled live test remains a separate production-traffic action requiring explicit authorization for the exact endpoint, route, direction, symbols, test window, evidence retention, stop conditions, and non-emergency path.
