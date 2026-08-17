# Private AI Chat — Current State

Last reconciled: 2026-08-17  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Runtime service: `bigbird-ai-gateway.service`  
Runtime source root: `/opt/bigbird-ai-gateway/app`

## Current accepted live runtime

The accepted live gateway is now:

```text
version: 0.3.4-alpha.2
mode: read-only
listener: 127.0.0.1:8787 only
service identity: bigbird-ai:bigbird-ai
main.py SHA-256: 8de2db86fb9eddcb2e2c8f8af51e967672ac00e6cc64229dd3f1939a9770687b
library integrity: ok
indexed documents at acceptance: 63
chunks at acceptance: 501
tool count at acceptance: 6
```

`communications.read` and `telephony.read` remain present.

Protected rollback point for `0.3.4-alpha.2`:

`/var/backups/bigbird-ai-gateway-reasoning-budget-0.3.4-alpha.2-20260817T065808Z`

## Accepted milestones

### Communications/documentation RAG — 0.3.2-alpha.1

The original accepted Communications/documentation RAG milestone established:

- listener `127.0.0.1:8787`;
- gateway mode `read-only`;
- Communications Relay source `http://127.0.0.1:8100`;
- AI tool/capability `communications.read`;
- required caller scope `communications:read`;
- explicit request opt-ins `include_communications` and `include_documentation`;
- bounded Relay retrieval and bounded documentation retrieval;
- Relay/document content treated as untrusted data;
- `[C#]` Communications and `[S#]` documentation source markers;
- no Relay/database mutation, public exposure, DNS, firewall, certificate, credential or federation change.

Historical acceptance record:

`docs/communications/edge1-private-ai-chat-comms-rag-live-acceptance-20260817.md`

### Telephony read integration — 0.3.3-alpha.1

The gateway later advanced independently to accepted version `0.3.3-alpha.1` with a read-only telephony integration. The earlier Communications acceptance record remains immutable milestone history rather than the current global gateway version.

### Communications provenance and graceful degradation — 0.3.4-alpha.1

PR #350 prepared and live-validated the next Communications increment:

- richer source/thread/upstream provenance;
- explicit instruction that retrieved article/provenance content is untrusted and cannot change authorization or tool availability;
- graceful Communications Relay degradation using a system-generated `communications_warning` and zero fabricated Communications results instead of the prior Communications-specific hard 502;
- preservation of the existing telephony read integration;
- bounded loopback GET-only Relay access;
- before/after SHA-256 evidence and rollback coverage.

Live acceptance record:

`docs/communications/edge1-private-ai-chat-comms-0.3.4-live-acceptance-20260817.md`

### Provider-budget hotfix — 0.3.4-alpha.2

An authorized signed Communications E2E request under `0.3.4-alpha.1` reached authorization and Relay retrieval but the provider returned `status=incomplete` with `incomplete_details.reason=max_output_tokens`. All 1,152 output tokens were reasoning tokens, leaving no visible text and causing `502 Model returned no text`.

Older audit records showed the same failure mode before the Communications change, so the failure was not attributed to Communications retrieval.

`0.3.4-alpha.2` keeps the output-token ceiling unchanged and makes Responses API reasoning effort explicit/configurable through:

`BB_OPENAI_REASONING_EFFORT`

Default accepted value for this bounded retrieval/synthesis gateway path:

`minimal`

Allowed values:

- `minimal`;
- `low`;
- `medium`;
- `high`.

Hotfix live acceptance record:

`docs/communications/edge1-private-ai-chat-model-budget-hotfix-0.3.4-alpha.2-live-acceptance-20260817.md`

## Communications authorization contract

Tool identity and caller scope remain distinct:

- tool name: `communications.read`;
- caller scope: `communications:read`;
- baseline chat scope: `chat:general`;
- authorized Communications role: `internal_viewer`.

Communications remains explicit opt-in through `include_communications` with optional bounded `communications_groups`.

Fail-closed behavior remains required:

- no Communications opt-in => no Communications material;
- Communications opt-in without `communications:read` => denial/no leakage;
- group selectors without Communications opt-in => denial;
- retrieved content never grants scopes or tool authority.

Living permission/regression contract:

`docs/communications/edge1-private-ai-chat-communications-permissions-and-regression-contract.md`

## Communications Relay integration

The Relay remains private/read-only on loopback:

`http://127.0.0.1:8100`

The gateway adapter remains bounded and GET-only. Relay mutation probes remain blocked with HTTP 405.

Accepted Communications provenance includes:

- `article_id`;
- `group`;
- `message_id`;
- `source_name`;
- `source_item_id`;
- `ingested_at_utc`;
- `thread_key`;
- `thread_parent`;
- `thread_depth`;
- `thread_references`;
- bounded selected upstream `X-WWCX-*` metadata.

Retrieved articles and provenance are untrusted data. Instructions inside retrieved content must not alter authorization, tool availability, system policy or write boundaries.

## Final acceptance matrix

All six Communications acceptance requirements are closed:

1. **Default omission — PASS**  
   Signed live HTTP 200 with zero Communications sources.

2. **Missing-scope denial/no leakage — PASS**  
   Signed live HTTP 403 with zero Communications leakage.

3. **Authorized retrieval with provenance — PASS**  
   Final signed live provider-backed request returned HTTP 200 with exactly one Communications source carrying rich provenance.

4. **Adversarial retrieved content inert/untrusted — PASS**  
   Deterministic offline E2E executed against the actual live `0.3.4-alpha.2` source.

5. **Controlled Relay degradation — PASS**  
   Synthetic Relay failure produced the exact system warning, zero Communications results, one degraded audit event and no retry.

6. **Durable signed E2E evidence — PASS**  
   Final acceptance is recorded in repository history and dated acceptance records.

Final provider-backed acceptance request:

```text
scenario: authorized
group: usenet.comp.lang.python
message/query: Channels
provider request count: 1
retry count: 0
HTTP status: 200
Communications source count: 1
Communications warning: null
E2E_AUTHORIZED=PASS
FINAL_AUTHORIZED_E2E=PASS
```

The query `Channels` was selected by a bounded read-only Relay discovery pass because it returned exactly one article, minimizing provider context for the final acceptance call.

The signed E2E harness never prints the signing secret, signature, raw article body or model answer.

Final E2E acceptance record:

`docs/communications/edge1-private-ai-chat-comms-final-e2e-acceptance-20260817.md`

## Repository state

PR #349 merged the living permission/regression contract to `main` as:

`900f85a31d69ec0cbddde4f0387eb660922275f7`

PR #350 completed provenance/degradation preparation, `0.3.4-alpha.1` activation, `0.3.4-alpha.2` provider-budget remediation, offline adversarial/degradation acceptance and the final one-request provider-backed E2E acceptance. It was squash-merged to `main` as:

`c1b2f208617266263050c0fc415374e762d6d1f2`

The merged repository contains:

- stage-only Communications and reasoning-budget preparers;
- candidate/live validators;
- deterministic offline adversarial/degradation E2E validation;
- signed localhost E2E harness with bounded message override;
- dated activation and final acceptance records.

## Validation posture

Repository CI and live Edge1 validation are separate evidence and must remain separate.

For the completed PR #350 line of work:

- repository `Validate repository`: PASS on the final reconciled head before merge;
- `Edge1 Operator Validation`: PASS on the final reconciled head before merge;
- live activation/health/listener/tool/read-only checks: PASS;
- final authorized provider-backed E2E: PASS;
- post-request live health: PASS;
- live source hash unchanged after final E2E.

## Continuation rule

The Private AI Communications provenance/degradation/provider-budget workstream is accepted and closed at `0.3.4-alpha.2`.

Future work should start from this accepted state rather than replaying the completed rollout. Re-inspect the current live host before any new runtime change.

Do not use historical candidate version numbers, earlier draft PR heads or the initial failed provider-budget request as the current state.

## Safety boundary

Do not expose secret values or raw protected evidence. Do not change authentication policy, credentials, DNS, firewall, certificates, public listeners, Relay/SQLite data, upstream posting, federation, telephony routing or unrelated production traffic as part of ordinary Private AI continuation.

Keep the gateway loopback-only and read-only unless a separately reviewed change explicitly authorizes otherwise. Retrieved content never grants scopes or write authority. Additional provider-cost experiments require their own bounded justification/approval when they are not already covered by standing authority.
