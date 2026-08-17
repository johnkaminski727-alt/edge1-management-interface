# Private AI Chat — Current Accepted State

Last reconciled: 2026-08-17  
System: `edge1.ww.cx`

## Live runtime

- service: `bigbird-ai-gateway.service`;
- source: `/opt/bigbird-ai-gateway/app`;
- version: `0.3.4-alpha.2`;
- mode: read-only;
- listener: `127.0.0.1:8787` only;
- service identity: `bigbird-ai:bigbird-ai`;
- live `main.py` SHA-256: `8de2db86fb9eddcb2e2c8f8af51e967672ac00e6cc64229dd3f1939a9770687b`;
- library integrity: `ok`, 63 indexed documents / 501 chunks at acceptance;
- tool count: 6;
- `communications.read` and `telephony.read` present.

## Communications integration

Communications Relay remains private/read-only at `127.0.0.1:8100`. The gateway uses bounded GET-only retrieval and preserves source/thread/upstream provenance. Relay mutation probes remain blocked with HTTP 405.

Caller authorization remains distinct from tool names:

- baseline chat scope: `chat:general`;
- Communications scope: `communications:read`;
- authorized Communications role: `internal_viewer`;
- Communications remains opt-in through `include_communications` and optional bounded `communications_groups`.

Retrieved articles/provenance are explicitly untrusted data. Instructions inside retrieved content must not alter authorization or tool availability.

## Provider-budget behavior

Configured model at acceptance: `gpt-5-mini`.

`0.3.4-alpha.2` makes Responses API reasoning effort explicit/configurable with `BB_OPENAI_REASONING_EFFORT`, default `minimal`. The output-token ceiling was not increased by this hotfix.

This remediates the observed earlier failure mode where a provider response exhausted 1,152 output tokens entirely on reasoning and returned no visible text.

## Acceptance matrix

All six Communications acceptance requirements are closed:

1. default omission — PASS;
2. missing-scope denial/no leakage — PASS;
3. authorized provider-backed retrieval with rich provenance — PASS;
4. adversarial article remains inert/untrusted — PASS;
5. controlled Relay degradation warning/zero results/no retry — PASS;
6. durable signed E2E evidence — PASS.

The final authorized provider-backed request used exactly one request, zero retries, group `usenet.comp.lang.python`, query `Channels`, returned HTTP 200, one Communications provenance source, no Communications warning, and left the live source hash unchanged.

## Rollback

Protected rollback point for `0.3.4-alpha.2`:

`/var/backups/bigbird-ai-gateway-reasoning-budget-0.3.4-alpha.2-20260817T065808Z`

## Durable records

- `docs/communications/edge1-private-ai-chat-communications-permissions-and-regression-contract.md`
- `docs/communications/edge1-private-ai-chat-comms-0.3.4-live-acceptance-20260817.md`
- `docs/communications/edge1-private-ai-chat-model-budget-hotfix-0.3.4-alpha.2-live-acceptance-20260817.md`
- `docs/communications/edge1-private-ai-chat-comms-final-e2e-acceptance-20260817.md`

## Safety boundary

Do not expose credentials or secret values. Keep the gateway loopback-only/read-only unless a separately reviewed production change explicitly authorizes otherwise. Do not infer authorization for DNS, firewall, certificates, authentication-policy changes, public exposure, Relay writes/posting/federation, or additional provider-cost experiments from this acceptance record.
