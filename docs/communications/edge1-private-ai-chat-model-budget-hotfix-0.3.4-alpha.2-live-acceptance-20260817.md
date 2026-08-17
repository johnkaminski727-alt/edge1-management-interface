# Edge1 Private AI Chat Model-Budget Hotfix 0.3.4-alpha.2 Live Acceptance

Accepted: 2026-08-17 06:58 UTC  
System: `edge1.ww.cx`

## Purpose

This record accepts the live activation of gateway `0.3.4-alpha.2`, a bounded follow-up to the accepted Communications runtime `0.3.4-alpha.1`.

The hotfix addresses a provider-response failure observed during the authorized signed Communications E2E test. The provider returned `status=incomplete` with `incomplete_details.reason=max_output_tokens`; all 1,152 returned output tokens were reasoning tokens and no visible text remained, causing the gateway to return `502 Model returned no text`. Older audit records showed the same failure mode before the Communications change, so the failure was not attributed to Communications retrieval.

The hotfix does not increase the output-token ceiling. It makes Responses API reasoning effort explicit and configurable through `BB_OPENAI_REASONING_EFFORT`, with a default of `minimal` for the bounded retrieval/synthesis gateway path and an allowlist of `minimal`, `low`, `medium`, and `high`.

## Accepted runtime state

- Service: `bigbird-ai-gateway.service`.
- Runtime source: `/opt/bigbird-ai-gateway/app`.
- Version: `0.3.4-alpha.2`.
- Mode: read-only.
- Listener: `127.0.0.1:8787` only.
- Library integrity: `ok`.
- Library state at acceptance: 63 indexed documents and 501 chunks.
- Tool count at health acceptance: 6.
- `communications.read` descriptor present.
- `telephony.read` descriptor present.
- Live `main.py` SHA-256: `8de2db86fb9eddcb2e2c8f8af51e967672ac00e6cc64229dd3f1939a9770687b`.

## Staging and source identity

The accepted candidate was staged separately from the live runtime and passed:

- stage-only preparer validation;
- `0.3.4-alpha.2` candidate contract validation;
- Python compilation under `/usr/bin/python3.11`;
- preserved Communications, telephony, baseline authorization, provider no-store, and no-text diagnostic checks;
- exact before/after hash contract.

Hash evidence:

```text
live alpha.1 before = 25861c46efd19a8feb6ef6286bef55d4743a4b1e048b4a40caeeea3d4dfeea4d
staged alpha.2      = 8de2db86fb9eddcb2e2c8f8af51e967672ac00e6cc64229dd3f1939a9770687b
```

The stage-only validation confirmed that no live source, service, provider, credential, or Relay state changed before activation.

## Guarded activation evidence

The activation created the protected rollback point:

```text
/var/backups/bigbird-ai-gateway-reasoning-budget-0.3.4-alpha.2-20260817T065808Z
```

The exact staged candidate was installed atomically. The installed source compiled as the `bigbird-ai` service user and passed the candidate validator before restart. Only `bigbird-ai-gateway.service` was restarted.

Post-restart evidence:

```text
ACTIVATION=PASS
live_version=0.3.4-alpha.2
live_main_sha256=8de2db86fb9eddcb2e2c8f8af51e967672ac00e6cc64229dd3f1939a9770687b
reasoning_default=minimal
provider_call_performed=false
output_token_ceiling_changed=false
relay_write_boundary=HTTP_405
```

Additional checks passed:

- health returned `ok=true`, `enabled=true`, `version=0.3.4-alpha.2`, `mode=read-only` and library integrity `ok`;
- live source passed the `0.3.4-alpha.2` candidate contract validator after restart;
- listener remained exactly `127.0.0.1:8787`;
- `communications.read` and `telephony.read` tool descriptors remained present;
- a Relay POST boundary probe remained blocked with HTTP 405;
- fresh service logs showed clean shutdown/startup and no traceback, error, critical exception, start failure, or address collision;
- final health passed;
- no OpenAI/provider request was made during staging or activation.

## Preserved boundaries

No DNS, firewall, certificate, authentication-policy, credential, Relay database, NNTP federation/posting/moderation, public exposure, or output-token-ceiling change was made.

The live source file remains owned `root:root` with mode `0644`; the service continues to run as `bigbird-ai:bigbird-ai`.

## E2E status carried forward

Signed live chat evidence already established before this activation:

1. ordinary chat without Communications opt-in: **PASS** — HTTP 200, zero Communications sources;
2. Communications opt-in without `communications:read`: **PASS** — HTTP 403, zero Communications leakage;
3. authorized Communications opt-in: authorization and Relay retrieval succeeded, but the provider response exhausted its output allowance on reasoning and returned no visible text. This is the provider-budget failure addressed by `0.3.4-alpha.2`; the authorized live provider E2E therefore remains pending.

The remaining work is to record deterministic offline acceptance for adversarial retrieved content and controlled Relay degradation, then perform at most one separately authorized live provider-backed Communications E2E request to close the authorized retrieval/provenance case.

## Source-control state

- PR: #350, `feature/private-ai-comms-provenance-degradation-prep-20260817`.
- Hotfix validator/preparation head before live acceptance: `823052a3a342a2aa5caf22ccef30acd82a395954`.
- Both `Validate repository` and `Edge1 Operator Validation` were green on that head before activation.
- PR #350 remains draft until the remaining E2E acceptance work is durably recorded.
