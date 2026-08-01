# DTMF Provider Evidence Intake

## Purpose

This intake contract prevents a carrier or interconnect from being added to the operational DTMF capability matrix based only on general SIP, Asterisk, FreePBX, DID, messaging, or account-activation statements.

A provider-specific DTMF claim requires retained technical evidence for the exact capability being recorded. General PBX compatibility is not evidence of RFC 4733 negotiation, SIP INFO, in-band survival, codec constraints, event range `0-15`, or extended `A-D` handling.

Assets:

```text
schemas/telephony/dtmf-provider-evidence.schema.json
schemas/telephony/dtmf-provider-technical-response.schema.json
examples/telephony/dtmf-provider-evidence.example.json
examples/telephony/dtmf-provider-technical-response.example.json
config/telephony/dtmf-provider-evidence/provider-candidate-001-public-documentation.json
config/telephony/dtmf-capability-matrix.json
tools/telephony/validate_dtmf_provider_evidence.py
tools/telephony/validate_dtmf_provider_technical_response.py
docs/telephony/dtmf-provider-technical-questionnaire-20260801.md
docs/telephony/dtmf-provider-response-intake.md
```

## Privacy boundary

The public repository record uses sanitized internal identifiers only. It must not retain:

- provider legal or trading names;
- customer or account numbers;
- email addresses, personal names, postal addresses, telephone numbers, or government identifiers;
- SIP usernames, SIP URIs, DIDs, IP addresses tied to a private interconnect, passwords, tokens, secrets, or API keys;
- private ticket URLs or URLs containing query strings;
- copies or excerpts of contracts, portal pages, private correspondence, identity documents, tax records, or credentials.

Private evidence stays in its authoritative restricted system. The repository record contains only sanitized evidence identifiers, source classes, review timestamps, retention classes, answer classifications, exact scopes, and short non-identifying summaries.

## Evidence classes

Accepted source classes are:

- `provider-public-documentation` — current provider documentation that directly states the technical behavior;
- `provider-private-correspondence` — a provider response that directly answers the technical question;
- `provider-portal-record` — a retained provider configuration or capability page;
- `executed-agreement` — a binding technical schedule or service description already accepted through a separately authorized process;
- `controlled-test-record` — evidence from a separately authorized controlled live test.

A provider account being active, a portal being accessible, or a product being described as compatible with Asterisk or FreePBX does not make the record matrix eligible.

## Required technical questions

For each sanitized provider and route, obtain evidence for the applicable direction:

1. Is RFC 4733 supported and required, optional, or unavailable?
2. Which `telephone-event` event range is negotiated: `0-11`, `0-15`, or another range?
3. Is SIP INFO supported for inbound, outbound, or both directions?
4. Is in-band DTMF supported, and under which codecs and transcoding conditions?
5. Are extended `A`, `B`, `C`, and `D` events accepted and preserved end to end?
6. Are there SBC, media-relay, codec, packetization, or regional exceptions?
7. Does the answer apply to the exact product, route type, and service direction under review?
8. What does the provider-hosted diagnostic destination actually validate?
9. Which Asterisk PJSIP DTMF and media settings are explicitly provider-recommended?

Do not infer an answer from generic SIP standards language or from a configuration guide that does not describe provider-network behavior.

The current provider-specific escalation and public-source answer table are recorded in:

```text
docs/telephony/dtmf-provider-technical-questionnaire-20260801.md
```

The question-by-question private-response classification and promotion procedure are recorded in:

```text
docs/telephony/dtmf-provider-response-intake.md
```

## Status rules

Each capability uses one of:

- `unknown`;
- `documented`;
- `controlled-test-passed`;
- `controlled-test-failed`.

Rules enforced by the evidence validator:

- `unknown` must have no evidence references;
- `documented` must reference provider or agreement evidence;
- a controlled-test status must reference a `controlled-test-record`;
- documented RFC 4733 support must state an event range;
- unknown in-band capability cannot claim codec constraints;
- an all-unknown record cannot be matrix eligible;
- a record cannot authorize a live test;
- private evidence cannot be marked for public repository retention.

Rules enforced by the technical-response validator:

- all nine questions must occur exactly once;
- pending answers remain unanswered, evidence-free, and unknown in scope;
- answered items must reference the retained restricted response;
- service guarantees must identify a concrete scope;
- configuration guidance and best-effort statements cannot authorize matrix promotion;
- test-required answers remain controlled-test-only;
- only a reviewed worksheet with a scoped service-guarantee answer may allow matrix consideration;
- every response worksheet keeps `live_test_authorized=false`.

## Validation

From the repository root:

```bash
python3 tests/test_validate_dtmf_provider_evidence.py
python3 tests/test_validate_dtmf_provider_technical_response.py

python3 tools/telephony/validate_dtmf_provider_evidence.py \
  examples/telephony/dtmf-provider-evidence.example.json

python3 tools/telephony/validate_dtmf_provider_evidence.py \
  config/telephony/dtmf-provider-evidence/provider-candidate-001-public-documentation.json

python3 tools/telephony/validate_dtmf_provider_technical_response.py \
  examples/telephony/dtmf-provider-technical-response.example.json
```

The synthetic evidence example deliberately records only general PBX compatibility and remains ineligible for the operational capability matrix.

The pending technical-response example contains all nine unanswered fields and cannot authorize a matrix update or live test.

The provider-public record is intentionally partial. It records only the public account-level statement that an automatic DTMF mode can fall back to in-band. It does not promote the provider's legacy RFC2833 label into an RFC 4733 claim because no event range is documented.

## Matrix promotion gate

A provider evidence record may be promoted into `config/telephony/dtmf-capability-matrix.json` only when:

- the exact provider and route have sanitized internal mappings;
- each promoted capability has a valid evidence reference;
- the evidence directly supports the claimed direction, transport mode, and event range;
- a private technical response has completed the response-intake classification when correspondence is used;
- only scoped service-guarantee answers are treated as candidates for documented capability claims;
- private source material remains outside the public repository;
- no credentials, customer identifiers, phone numbers, or private endpoints are introduced;
- repository validation passes;
- a controlled-test claim, when used, comes from a separately authorized test with retained evidence.

Promotion records capability evidence only. It does not activate a trunk, endpoint, route, DID, service, account, emergency-calling path, or production traffic.

## Current decision

A sanitized provider candidate now has one matrix-eligible capability: provider-public documentation directly states an account-level automatic fallback to in-band DTMF. The matrix therefore records `inband.status=documented` with no codec claim.

The same documentation uses the legacy RFC2833/AVT label but does not state an event range. Under the repository evidence policy, RFC 4733 remains `unknown`. SIP INFO, extended `A-D`, exact route directionality, codec and transcoding behavior, and end-to-end carrier interoperability also remain `unknown` or `partially-documented` as applicable.

A technical questionnaire covering every unresolved field was sent to provider support on `2026-08-01T20:39:00Z`. The private correspondence remains in the authoritative mailbox. No additional matrix capability will be promoted until a provider response directly supports the exact claim and passes the technical-response, privacy, and cross-record validation gates.

No provider configuration, purchase, contract acceptance, call, DTMF transmission, route change, or production activation is authorized by this intake package.
