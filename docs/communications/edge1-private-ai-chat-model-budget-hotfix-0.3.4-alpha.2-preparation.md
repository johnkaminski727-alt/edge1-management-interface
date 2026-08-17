# Edge1 Private AI Model Budget Hotfix 0.3.4-alpha.2 Preparation

Status: staged engineering preparation only  
Prepared: 2026-08-17  
Baseline: `0.3.4-alpha.1`  
Target candidate: `0.3.4-alpha.2`

## Why this hotfix exists

During the signed Communications end-to-end acceptance run, the default omission case passed with HTTP 200 and zero Communications sources, and the missing-`communications:read` case failed closed with HTTP 403 and zero leakage. The authorized Communications request passed signing, caller authorization and Relay retrieval, but the provider response completed with no visible text.

The gateway audit record identified the precise provider state:

- response status: `incomplete`;
- incomplete reason: `max_output_tokens`;
- output types: reasoning only;
- visible content types: none;
- output tokens: 1,152;
- reasoning tokens: 1,152.

A direct loopback Relay retrieval independently returned five matching `usenet.comp.lang.python` results with article/group/message/source/thread provenance. Therefore the failure is downstream of Communications authorization/retrieval and is not a Relay, signing or permission defect.

Historical gateway audit entries show the same reasoning-only output-budget exhaustion under older gateway versions, so the defect predates the 0.3.4 Communications provenance change.

## Hotfix behavior

The hotfix keeps the existing `BB_MAX_OUTPUT_TOKENS` mechanism and does not increase its source default. Instead it makes Responses API reasoning effort explicit:

- new non-secret configuration: `BB_OPENAI_REASONING_EFFORT`;
- default: `minimal`;
- accepted values for the current pre-GPT-5.1 model generation: `minimal`, `low`, `medium`, `high`;
- invalid values fail closed during gateway startup;
- provider request gains `"reasoning": {"effort": OPENAI_REASONING_EFFORT}`;
- candidate version becomes `0.3.4-alpha.2`.

The current configured model observed during the acceptance investigation is `gpt-5-mini`.

This targets the observed failure mechanism directly: hidden reasoning tokens were consuming the available output budget before any visible answer could be produced.

## Stage-only preparation

From a current checkout of this PR branch, an authenticated Edge1 operator may stage the candidate with:

```bash
python3 tools/prepare_private_ai_reasoning_budget_fix.py \
  --source-root /opt/bigbird-ai-gateway/app \
  --output-root /tmp/bigbird-ai-reasoning-budget-0.3.4-alpha.2-stage
```

The preparer:

1. requires the live/source baseline to identify as `0.3.4-alpha.1`;
2. verifies the existing OpenAI model/output-budget, no-text audit and Communications authorization markers;
3. reads only `main.py`;
4. writes a patched `main.py` under the separate staging directory;
5. compiles the staged source;
6. writes `hotfix-report.json` with before/after SHA-256 values and explicit non-actions.

It has no apply mode.

## Non-mutation guarantees

The preparer does not:

- modify `/opt/bigbird-ai-gateway/app`;
- read `/etc/bigbird-ai-gateway.env` or any environment value;
- access `OPENAI_API_KEY`, `BB_RELAY_SECRET`, or other credentials;
- contact OpenAI or another provider;
- contact the Communications Relay;
- restart/reload `bigbird-ai-gateway.service`;
- change the output-token ceiling;
- alter authentication, tool scopes, Relay behavior, telephony behavior, listeners, DNS, firewall or certificates.

`tests/validate_private_ai_reasoning_budget_fix.py` exercises the stage-only behavior with a synthetic baseline and verifies that the source remains byte-for-byte unchanged.

## Acceptance sequence

Before any live activation:

1. CI must pass on the exact candidate-preparation commit;
2. run the hotfix preparer against the exact live `0.3.4-alpha.1` source;
3. inspect the hash report and diff;
4. compile and statically validate the staged candidate under `/usr/bin/python3.11`;
5. create a protected rollback backup;
6. apply only the reviewed `main.py` candidate and restart only `bigbird-ai-gateway.service` under the existing guarded activation boundary;
7. verify health, version, loopback listener, read-only mode, library integrity, Relay GET-only posture and telephony preservation;
8. do not make a provider request until separately authorized after activation;
9. with explicit provider-use approval, perform one bounded authorized Communications E2E request and verify visible text plus Communications provenance;
10. record a separate durable E2E acceptance only after adversarial-content and controlled-degradation checks also pass.

## Source basis

OpenAI's Responses API documentation states that `max_output_tokens` includes both visible output and reasoning tokens. OpenAI also documents configurable reasoning effort, with lower effort reducing reasoning-token usage; models before GPT-5.1 default to medium reasoning effort and do not support `none`. This hotfix therefore uses `minimal` as the bounded retrieval/synthesis default rather than increasing the token ceiling.
