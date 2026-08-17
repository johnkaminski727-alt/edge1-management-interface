# Edge1 Private AI Chat Communications Final E2E Acceptance

Accepted: 2026-08-17 07:17 UTC  
System: `edge1.ww.cx`  
Gateway: `0.3.4-alpha.2`

## Result

The Private AI Chat Communications acceptance contract is complete.

The final separately authorized provider-backed signed localhost request passed against the live gateway with exactly one provider request and zero retries.

Final request scope:

```text
scenario=authorized
group=usenet.comp.lang.python
message=Channels
provider_request_count=1
retry_count=0
```

Observed sanitized response:

```text
http_status=200
mode=read-only
communications_sources_count=1
communications_warning=null
E2E_AUTHORIZED=PASS
FINAL_AUTHORIZED_E2E=PASS
```

The single Communications source exposed the expected rich provenance key set, including:

- `article_id`;
- `group`;
- `message_id`;
- `source_id`;
- `source_name`;
- `source_item_id`;
- `ingested_at_utc`;
- `thread_key`;
- `thread_parent`;
- `thread_depth`;
- `thread_references`;
- `upstream`.

The harness intentionally did not print the model answer, article body, signing secret, key value, or signature.

## Provider-budget remediation acceptance

The earlier authorized `0.3.4-alpha.1` request failed because the provider returned `status=incomplete` / `reason=max_output_tokens` after all 1,152 output tokens were consumed by reasoning and no visible text remained.

Live `0.3.4-alpha.2` keeps the output-token ceiling unchanged and makes reasoning effort explicit/configurable through `BB_OPENAI_REASONING_EFFORT`, defaulting to `minimal` for this bounded retrieval/synthesis path.

The successful final E2E proves that the live `reasoning=minimal` configuration can produce a visible successful answer while retaining one non-empty Communications provenance source.

## Full acceptance matrix

1. Default chat without Communications opt-in: **PASS** — signed live HTTP 200, zero Communications sources.
2. Communications opt-in without `communications:read`: **PASS** — signed live HTTP 403, zero Communications leakage.
3. Authorized Communications retrieval with provenance: **PASS** — signed live HTTP 200, one Communications source with rich provenance.
4. Adversarial retrieved content remains inert/untrusted: **PASS** — deterministic offline E2E against the actual live source.
5. Controlled Relay failure degrades safely: **PASS** — exact system warning, zero Communications results, one degraded audit event, no retry.
6. Durable/signed E2E acceptance evidence: **PASS** — this record plus the dated activation/offline acceptance records and PR history.

## Post-request integrity

After the single provider-backed request:

```text
POST_PROVIDER_HEALTH=PASS
live_version=0.3.4-alpha.2
live_main_sha256=8de2db86fb9eddcb2e2c8f8af51e967672ac00e6cc64229dd3f1939a9770687b
LIVE_SOURCE_UNCHANGED=PASS
additional_provider_requests_performed=false
credential_values_printed=false
```

The live gateway remained read-only and healthy. No source modification, service restart, DNS/firewall/certificate/authentication-policy change, Relay write, NNTP posting/federation change, credential disclosure, or additional provider request occurred.

## Related records

- `docs/communications/edge1-private-ai-chat-communications-permissions-and-regression-contract.md`
- `docs/communications/edge1-private-ai-chat-comms-0.3.4-live-acceptance-20260817.md`
- `docs/communications/edge1-private-ai-chat-model-budget-hotfix-0.3.4-alpha.2-live-acceptance-20260817.md`
- `tests/validate_private_ai_comms_e2e_offline.py`
- `tools/private_ai_signed_chat_e2e.py`
- `tests/validate_private_ai_signed_chat_harness.py`

## Merge readiness

All functional acceptance blockers for PR #350 are closed. The PR may leave draft state after CI passes on this final acceptance record and may be squash-merged using the reviewed branch head.
