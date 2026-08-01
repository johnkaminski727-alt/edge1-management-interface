# DTMF Provider Technical-Response Intake

## Purpose

This package converts a direct provider response into a privacy-minimized, question-by-question worksheet before any capability is considered for the public DTMF matrix.

Assets:

```text
schemas/telephony/dtmf-provider-technical-response.schema.json
examples/telephony/dtmf-provider-technical-response.example.json
tools/telephony/validate_dtmf_provider_technical_response.py
tests/test_validate_dtmf_provider_technical_response.py
```

The worksheet is not a copy of private correspondence. It stores only sanitized internal identifiers, a restricted evidence reference, answer classifications, exact service scopes, and short non-identifying summaries.

## Required questions

Every worksheet contains exactly one answer slot for each unresolved provider question:

1. RFC 4733 or legacy RFC2833 directionality;
2. advertised, accepted, and preserved event range;
3. extended `A-D` handling;
4. SIP INFO support and directionality;
5. in-band codec and transcoding constraints;
6. automatic fallback or interworking behavior;
7. route, server, SBC, regional, and upstream exceptions;
8. provider diagnostic destination scope;
9. explicit Asterisk PJSIP recommendations.

A missing, ambiguous, or indirect answer remains `unanswered`. Device capabilities, troubleshooting suggestions, and generic configuration examples do not become carrier service guarantees.

## Response states

- `pending` — no direct provider response has been received;
- `received` — a response exists in the restricted mailbox but has not completed technical review;
- `reviewed` — each answer has been classified and the sanitized worksheet has passed validation.

Only a reviewed worksheet can allow consideration of a matrix update.

## Answer classifications

Each question records:

- `answer_status` — `unanswered`, `documented`, `not-supported`, `conditional`, or `test-required`;
- `evidence_strength` — `none`, `service-guarantee`, `best-effort`, `configuration-guidance`, or `controlled-test-only`;
- `scopes` — account-level, inbound, outbound, internal, or unknown;
- `details` — a short sanitized summary;
- `evidence_refs` — the restricted provider-response evidence identifier.

The validator requires:

- unanswered items to remain evidence-free and scoped only as unknown;
- answered items to reference the retained restricted response;
- service guarantees to identify a concrete scope;
- test-required answers to use controlled-test-only evidence strength;
- a pending or merely received response to keep `matrix_update_allowed=false`;
- a matrix update decision to have at least one reviewed, concretely scoped service-guarantee answer;
- `live_test_authorized=false` in every worksheet.

A response that says behavior is common, recommended, configurable, best-effort, or test-dependent does not satisfy the service-guarantee gate.

## Privacy boundary

The public worksheet must not retain:

- provider identity;
- account, customer, ticket, or telephone identifiers;
- email addresses or personal names;
- SIP usernames, URIs, endpoints, IP addresses, credentials, secrets, or tokens;
- private message text, headers, attachments, or portal URLs;
- contracts or identity documents.

The original response remains in the restricted mailbox. The validator reuses the provider-evidence sensitive-text and prohibited-key checks.

## Validation

From the repository root:

```bash
python3 tests/test_validate_dtmf_provider_technical_response.py

python3 tools/telephony/validate_dtmf_provider_technical_response.py \
  examples/telephony/dtmf-provider-technical-response.example.json
```

Expected pending result:

```text
response_state=pending
matrix_update_allowed=false
live_test_authorized=false
```

## Public-source exhaustion result

The provider-controlled public material confirms an account-level automatic RTP-event mode with in-band fallback, configurable codec allowlists, and a provider-hosted diagnostic destination.

The public Asterisk PJSIP configuration guide uses `ulaw` and mentions optional `g729`, but does not set a PJSIP DTMF mode. Public SIP INFO references occur in client-feature or troubleshooting material and therefore do not establish a provider-network SIP INFO guarantee.

Accordingly, the direct technical response remains necessary for directionality, event range, extended events, SIP INFO, codec survival, transcoding, interworking, route exceptions, diagnostic path scope, and provider-recommended PJSIP DTMF settings.

## Operational boundary

This intake package does not contact the provider, alter an account setting, create an endpoint, configure a trunk, originate a call, transmit DTMF, activate a route, or authorize a controlled live test.
