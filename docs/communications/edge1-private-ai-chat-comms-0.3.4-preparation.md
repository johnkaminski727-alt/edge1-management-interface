# Edge1 Private AI Communications Upgrade Preparation

Status: staged engineering preparation only  
Prepared: 2026-08-17  
Target candidate: `0.3.4-alpha.1`

## Purpose

This runbook describes the non-mutating preparation step for the next Private AI Communications integration increment. It does **not** authorize or perform a deployment.

The candidate increment is intended to preserve the accepted read-only boundary while improving:

- source, thread and upstream provenance carried from the Communications Relay into AI source metadata;
- explicit prompt-injection isolation for retrieved communications content;
- graceful Relay degradation so an unavailable Relay produces no fabricated communications data and does not necessarily terminate an otherwise safe chat response;
- response/audit metadata indicating degraded communications retrieval.

The current verified upgrade baseline is gateway `0.3.3-alpha.1`, which already includes the accepted telephony read integration. The preparer fails closed if that baseline is not present.

## Stage-only command

From a current checkout of `edge1-management-interface`, an authenticated Edge1 operator may run:

```bash
python3 tools/prepare_private_ai_comms_upgrade.py \
  --source-root /opt/bigbird-ai-gateway/app \
  --output-root /tmp/bigbird-ai-comms-0.3.4-stage
```

This command is designed to:

1. read only `main.py` and `integrations/communications_relay/client.py` from the gateway source tree;
2. verify the expected `0.3.3-alpha.1` and telephony/communications baseline markers;
3. generate candidate copies under the separate output directory;
4. syntax-check the generated Python source with `compile()`;
5. write `upgrade-report.json` containing before/after SHA-256 values and an explicit `not_performed` list.

It does not contain an apply mode.

## Non-mutation guarantees

The preparer intentionally does **not**:

- modify `/opt/bigbird-ai-gateway/app`;
- import or execute the gateway application;
- inspect environment variables or secret values;
- contact the AI provider;
- contact the Communications Relay;
- open network connections;
- restart or reload `bigbird-ai-gateway.service`;
- deploy candidate files;
- change authentication, DNS, firewall, certificates, listeners, Relay data or telephony state.

The repository validator `tests/validate_private_ai_comms_upgrade_preparer.py` checks these design properties using a synthetic `0.3.3-alpha.1` source tree and verifies that the source remains byte-for-byte unchanged.

## Candidate behavior

The staged candidate preserves the existing GET-only loopback Communications Relay adapter while carrying additional bounded metadata:

- `source_name`;
- `source_item_id`;
- `ingested_at_utc`;
- `thread_key`;
- `thread_parent`;
- `thread_depth`;
- `thread_references`;
- selected bounded `X-WWCX-Upstream-*` provenance fields.

Retrieved article and provenance fields remain untrusted data. They cannot grant authorization, enable write tools, alter tool availability or authorize Relay mutations.

If the Relay read fails, the candidate records a bounded audit error, returns no communications articles, and supplies a system-generated `communications_warning` rather than fabricating source data. This behavior must still be exercised end to end before live acceptance.

## Required review before any live change

Staging success is not deployment authorization. Before any live application:

1. run the repository contract validator against the deployed gateway source tree;
2. run this preparer against that exact source tree;
3. inspect the generated hash report and candidate diff;
4. verify telephony integration and all unrelated gateway behavior are preserved;
5. add/execute targeted source-controlled regression coverage against the staged candidate;
6. create a protected backup and rollback point;
7. obtain any approval required for a gateway service restart or production activation;
8. apply only the reviewed candidate files;
9. verify service health, loopback listener, tool descriptors, authorization gates, Relay read-only posture and no unintended listener/data changes;
10. record a separate dated live acceptance.

If the baseline markers differ, the preparer must fail rather than guessing how to patch an unknown gateway version.

## Related records

- `docs/communications/edge1-private-ai-chat-communications-permissions-and-regression-contract.md`
- `docs/communications/edge1-private-ai-chat-comms-rag-live-acceptance-20260817.md`
- `.agent/private-ai-chat.md`
- `tests/validate_private_ai_gateway_contract.py`
- `tests/validate_private_ai_comms_upgrade_preparer.py`
