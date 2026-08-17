# Edge1 Private AI Chat Communications Permission and Regression Contract

Status: living engineering contract  
Established: 2026-08-17  
Applies to: private Edge1 AI Chat communications/documentation retrieval

## Purpose

This document defines the authorization, consent, failure and regression requirements for the accepted read-only AI Chat integration with the Edge1 Communications Relay.

It complements the dated live-acceptance record. The acceptance record remains immutable operational history; this file is the living contract for follow-on gateway implementation and tests.

## Security boundary

The integration remains read-only-first.

- `communications.read` grants retrieval only. It does not grant posting, deletion, moderation, ingestion, relay/database mutation, service control or infrastructure changes.
- Communications data is excluded by default. A request must explicitly opt in to communications retrieval.
- The caller must also hold `communications.read`; an opt-in flag alone never authorizes access.
- Retrieved article/document text is untrusted content. It cannot grant scopes, change tool permissions or authorize a write.
- Relay access remains through the loopback read-only API. Do not add direct SQLite write access or mutation-capable Relay methods to satisfy this contract.
- Secret values, credential files, raw protected evidence and unrelated private stores remain outside ordinary RAG.

## Permission and consent behavior

### Why the scope exists

`communications.read` separates ordinary private AI Chat use from access to locally retained communications/news material. It provides a narrow authorization boundary so communications retrieval can be enabled without expanding the bot into a general communications operator.

### Request flow

1. A normal request without communications opt-in behaves exactly as before and omits communications context.
2. A request that opts into communications retrieval is evaluated against the caller's current authorization.
3. If `communications.read` is present, the gateway may retrieve bounded read-only communications context.
4. If the scope is absent, the request must fail closed for the communications operation and return no communications material.
5. The gateway must never silently add, mint, infer or elevate the missing scope.

### User-facing consent/retry guidance

If the product has an interactive authorization/consent surface, it should explain that the scope permits the private assistant to read bounded Communications Relay/News Reader material for answering the current request. It must not describe the scope as permission to post or modify communications.

When a request is rejected for missing scope:

- explain that `communications.read` is required for communications retrieval;
- do not expose partial communications results;
- do not loop on automatic retries with the same insufficient token;
- retry only after the caller deliberately completes the product's normal authorization/consent flow and receives authorization containing the scope;
- do not log or display token, cookie, credential or secret values while diagnosing authorization.

If no interactive consent mechanism exists, fail closed and give an operator-safe explanation rather than changing authentication policy automatically.

## Regression contract

The gateway source repository must carry automated tests for the following cases. Test names may follow the gateway framework, but these behaviors are mandatory.

### R1 — default omission

Given a valid ordinary AI Chat caller, a normal context/chat request that does not opt into communications must not retrieve or return Communications Relay material.

### R2 — opt-in without scope rejects

Given a caller without `communications.read`, a request with communications opt-in enabled must return an authorization failure (non-success response or equivalent framework denial) and no communications content.

The test must not depend on a specific status code unless the gateway API contract defines one.

### R3 — opt-in with scope succeeds read-only

Given a caller with `communications.read`, an explicit communications opt-in may retrieve bounded communications context. Returned records must preserve available provenance such as group/article/message/source identifiers.

### R4 — chat briefing uses the same gate

Any chat/briefing path that can inject communications context must enforce the same explicit opt-in plus `communications.read` requirement. A secondary prompt-building path must not bypass the context endpoint's authorization rule.

### R5 — no mutation capability

The AI-facing Communications Relay adapter must expose read operations only. Regression coverage must prove that ordinary AI Chat tool dispatch cannot invoke Relay POST/PUT/PATCH/DELETE behavior or equivalent database mutation.

### R6 — bounded retrieval

Search/list operations must enforce existing bounds for result count, pagination and context size. Caller input must not produce unbounded article ingestion into the prompt.

### R7 — prompt-injection fixture

A fixture containing article/document text that instructs the model to ignore policy, acquire permissions, call a write tool, reveal secrets or modify the Relay must remain inert as data. It may be summarized or quoted as content but cannot change authorization or tool availability.

### R8 — graceful Relay degradation

If the loopback Relay API is unavailable or returns an error, the assistant must degrade cleanly: no state mutation, no permission elevation, no retry storm, and no fabricated communications result. Documentation-only or non-communications chat may continue when safe.

### R9 — provenance preservation

Where communications content contributes to an answer, tests must verify that source/thread provenance survives retrieval into the assistant response metadata or source trail according to the gateway's established schema.

### R10 — secret/path exclusion

Documentation retrieval tests must demonstrate that credential locations, raw protected evidence and other excluded roots cannot enter ordinary AI Chat retrieval merely because documentation retrieval is enabled.

## Acceptance gate for the next gateway change

A follow-on gateway change is ready for acceptance only when:

1. the source repository/checkout for the gateway is identified and the above tests live beside the implementation;
2. targeted regression tests pass from source control;
3. the authorization denial and authorized opt-in paths are exercised end to end;
4. prompt-injection and Relay-degradation fixtures pass;
5. no new write-capable Relay tool is introduced;
6. live validation, if performed, remains loopback-only and read-only;
7. service/config/database state is verified unchanged except for the explicitly accepted gateway change;
8. the signed end-to-end chat acceptance is recorded separately as dated operational evidence.

## Out of scope / separately gated

This contract does not authorize:

- cloud/model-provider credential wiring;
- authentication-policy redesign;
- new OAuth clients, token issuance or credential rotation;
- public exposure, DNS, firewall or certificate changes;
- Relay or SQLite writes;
- upstream posting, moderation or federation;
- service restarts or production activation beyond an explicitly approved implementation step.

## Related records

- `docs/communications/edge1-private-ai-chat-comms-rag-live-acceptance-20260817.md`
- `docs/handoff/edge1-private-ai-chat-comms-integration-handoff-20260817.md`
- `docs/communications/edge1-comms-relay-news-reader.md`
- `docs/communications/README.md`
