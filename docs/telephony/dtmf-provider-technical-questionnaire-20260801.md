# DTMF Provider Technical Questionnaire — 2026-08-01

## Purpose

This record documents the provider-specific technical questions required to advance the sanitized DTMF capability matrix beyond the currently accepted partial state.

The provider and route remain represented only by sanitized internal identifiers:

```text
provider_id=provider-candidate-001
route_id=route-candidate-001
```

No provider name, account number, ticket number, email address, telephone number, SIP URI, credential, private endpoint, or private correspondence content is retained in this public repository record.

## Public-source findings

Provider-controlled public documentation supports only the following statements:

1. an account or subaccount can select a DTMF mode;
2. the automatic mode uses the provider's legacy `RFC2833 (AVT)` label;
3. the automatic mode can fall back to in-band when the other end does not support that RTP-event mode;
4. account and subaccount codec allowlists are configurable;
5. a provider-hosted DTMF diagnostic destination exists;
6. public troubleshooting guidance may recommend trying in-band or AVT device settings when diagnosing DTMF problems;
7. the public Asterisk PJSIP example uses `ulaw` and mentions optional `g729`, but does not set a PJSIP DTMF mode;
8. public SIP INFO references occur in client feature descriptions and troubleshooting guidance, not in a provider-network service guarantee.

These statements do not establish an RFC 4733 event range, direction-specific support, SIP INFO service support, codec survival, transcoding behavior, extended `A-D`, or end-to-end carrier interoperability.

## Current evidence decision

| Question | Current answer | Evidence boundary |
| --- | --- | --- |
| Is an RTP-event DTMF mode available? | `documented` under the provider's legacy `RFC2833/AVT` terminology | No RFC 4733 event range is stated. |
| Does AUTO fall back to in-band? | `documented` at account-setting level | Trigger details, directionality, translation, and route applicability are not stated. |
| Is RFC 4733 supported inbound and outbound? | `unknown` | Public text does not distinguish customer-to-provider and provider-to-customer behavior. |
| Which events are advertised or accepted? | `unknown` | No `0-11`, `0-15`, payload, or event-list statement is published. |
| Are `A-D` supported end to end? | `unknown` | A diagnostic destination alone does not prove extended-event handling. |
| Is SIP INFO supported? | `unknown` | Client feature and troubleshooting references do not constitute a provider service guarantee. |
| Which codecs preserve in-band DTMF? | `unknown` | Configurable codec allowlists and audio troubleshooting do not prove DTMF survival through any codec or transcoder. |
| Does the provider translate between DTMF modes? | `unknown` | The published fallback wording does not specify pass-through versus interworking. |
| Are there direction, route, POP, SBC, regional, encryption, or upstream-carrier exceptions? | `unknown` | No exact applicability statement is published. |
| What does the diagnostic destination validate? | `partially-documented` | Its existence and general purpose are documented; recognized digits and path scope are not. |
| Which Asterisk PJSIP settings are provider-recommended? | `partially-documented` for media only | The public example uses `ulaw` and mentions optional `g729`, but omits `dtmf_mode`, event range, payload, `auto_info`, and direct-media guidance. |

## Provider escalation

A technical questionnaire was sent to provider support on `2026-08-01T20:39:00Z`. The retained private correspondence remains in the authoritative mailbox and is not copied into the public repository.

The escalation asks for provider-specific answers to:

1. RTP `telephone-event` support in each direction for inbound DID and outbound PSTN service;
2. advertised, accepted, and preserved event ranges, including events `12-15` and keys `A-D`;
3. SIP INFO directionality, content type, body format, and applicable product or route types;
4. supported and recommended in-band codecs, including packetization, silence suppression, transcoding, media-relay, and direct-media limits;
5. whether AUTO fallback is per-call SDP behavior, an account mode, pass-through, or protocol translation;
6. differences by DID type, direction, country, route class, POP/server, SBC, upstream carrier, encrypted media, and internal calls;
7. the diagnostic destination's recognized digits and whether it validates one leg, return path, or end-to-end behavior;
8. recommended Asterisk PJSIP mode, payload, event range, codec, and direct-media settings.

The request explicitly asks the provider to distinguish:

- documented service guarantees;
- best-effort or commonly observed behavior;
- behavior that can only be established by a controlled live test.

## Response processing

The validated response worksheet and promotion gates are documented in:

```text
docs/telephony/dtmf-provider-response-intake.md
schemas/telephony/dtmf-provider-technical-response.schema.json
examples/telephony/dtmf-provider-technical-response.example.json
tools/telephony/validate_dtmf_provider_technical_response.py
```

No additional capability may be promoted while the response is pending.

When a response arrives:

1. retain the original message in the restricted mailbox;
2. create only a sanitized technical-response worksheet;
3. classify each answer as a service guarantee, best-effort statement, configuration guidance, or controlled-test-only result;
4. map each answer to an exact capability and scope;
5. leave ambiguous or unanswered fields as `unknown`;
6. do not treat configuration advice as proof of carrier or end-to-end interoperability;
7. do not authorize a live test through the response or evidence record;
8. run response-intake, provider-evidence, privacy, cross-record matrix, and repository validations before merge.

## Operational boundary

Sending the questionnaire and preparing the response intake did not originate a call, transmit DTMF, change an endpoint, trunk, route, DID, dialplan, account setting, codec, service, listener, firewall rule, DNS record, certificate, emergency-calling path, or production traffic.

Current accepted state remains:

```text
inband_status=documented
rfc4733_status=unknown
rfc4733_event_range=unknown
sip_info_status=unknown
extended_abcd_status=unknown
carrier_interoperability=partially-documented
live_test_authorized=false
```
