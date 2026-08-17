# Private AI Chat — Current State

Last reconciled: 2026-08-17  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Runtime service: `bigbird-ai-gateway.service`  
Runtime source root: `/opt/bigbird-ai-gateway/app`

## Accepted milestones

### Communications/documentation RAG

Accepted live at gateway version `0.3.2-alpha.1`:

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

### Telephony read integration

The gateway later advanced independently to accepted version `0.3.3-alpha.1` with a read-only telephony integration. The communications acceptance record remains the immutable history of the `0.3.2-alpha.1` milestone rather than the current global gateway version.

## Current repository hardening

Draft PR #349 establishes the living Communications permission/regression contract, adversarial fixture and repository-owned validator:

- `docs/communications/edge1-private-ai-chat-communications-permissions-and-regression-contract.md`;
- `tests/fixtures/private_ai/communications_prompt_injection.json`;
- `tests/validate_private_ai_gateway_contract.py`.

The validator distinguishes the dot-form tool name `communications.read` from the colon-form authorization scope `communications:read` and checks the accepted read-only gateway contract: explicit opt-in, authorization gate, bounds, secret filtering, untrusted-content marker, bounded Relay failure handling, provenance response, loopback-only default, GET-only Relay requests and absence of write-capable/direct-SQLite/code-execution escape hatches in the Communications adapter.

PR #349 head at this reconciliation point:

`1a0cce072bf0bfff199fdd827e63364ef6d940cb`

CI on that head:

- `Validate repository` run 1284: PASS;
- `Edge1 Operator Validation` run 1116: PASS;
- `tests/validate_private_ai_gateway_contract.py`: PASS in the repository validation log.

The GitHub workflows are repository CI only; they do not constitute live Edge1 validation.

## Verified Relay provenance available to the gateway

The loopback News Reader API already exposes richer metadata than the initial gateway adapter preserves. Available bounded article-list fields include:

- `source_name`;
- `source_item_id`;
- `thread_key`;
- `thread_parent`;
- `thread_depth`;
- `thread_references`.

Article detail also exposes `source_name`, `source_item_id`, `ingested_at_utc` and stored headers. Selected `X-WWCX-*` headers can preserve upstream provenance without contacting upstream providers or reading credentials.

## Prepared next increment — candidate 0.3.4-alpha.1

Draft PR #350 is the separate stage-only implementation preparation and is ordered after PR #349.

Branch:

`feature/private-ai-comms-provenance-degradation-prep-20260817`

Head:

`15ad93936a9aa9943e971ab42ecbff45abd2de51`

Files:

- `tools/prepare_private_ai_comms_upgrade.py`;
- `tests/validate_private_ai_comms_upgrade_preparer.py`;
- `docs/communications/edge1-private-ai-chat-comms-upgrade-preparation.md`.

The preparer has no apply mode. Against an exact `0.3.3-alpha.1` source baseline it stages candidate copies outside the gateway source tree and prepares:

- target version `0.3.4-alpha.1`;
- richer source/thread/upstream provenance;
- explicit instruction that retrieved article/provenance content is untrusted and cannot change authorization or tool availability;
- graceful Communications Relay degradation using a system-generated `communications_warning` and zero fabricated communications results instead of the current communications-specific HTTP 502 hard fail;
- preservation of the existing telephony read integration;
- before/after SHA-256 evidence.

The preparer intentionally performs no source-tree mutation, gateway import/execution, environment/secret inspection, network/Relay/provider access, service restart or deployment.

PR #350 CI:

- `Validate repository` run 1285: PASS;
- `Edge1 Operator Validation` run 1117: PASS;
- `tests/validate_private_ai_comms_upgrade_preparer.py`: PASS in the repository validation log;
- `compileall`: PASS.

## Repository-safe work completed

- [x] distinguish `communications.read` tool from `communications:read` caller scope;
- [x] document opt-in and fail-closed permission behavior;
- [x] add source-controlled gateway contract validation;
- [x] add adversarial communications prompt-injection fixture with thread/source provenance;
- [x] reject Relay write methods and direct SQLite/code-execution escape hatches in the adapter contract;
- [x] document richer source/thread provenance available from the News Reader API;
- [x] prepare a stage-only richer-provenance candidate;
- [x] prepare graceful Relay degradation without fabricated communications data;
- [x] preserve telephony integration in the candidate contract;
- [x] validate both draft PR heads in repository CI.

## Exact next live-safe actions

An authenticated Edge1 execution path is now the remaining blocker.

First run the static contract validator against the deployed source tree:

```bash
cd /opt/edge1-management-interface
python3 tests/validate_private_ai_gateway_contract.py \
  --gateway-root /opt/bigbird-ai-gateway/app
```

Then, if that passes and the exact runtime source is still the expected `0.3.3-alpha.1` baseline, stage the candidate without modifying production:

```bash
rm -rf /tmp/bigbird-ai-comms-0.3.4-stage
python3 tools/prepare_private_ai_comms_upgrade.py \
  --source-root /opt/bigbird-ai-gateway/app \
  --output-root /tmp/bigbird-ai-comms-0.3.4-stage
```

Review the generated `upgrade-report.json`, SHA-256 values and candidate diff before any application.

Any live application remains a separate step: inspect the exact source/working state, back up first, apply only the reviewed files, restart only `bigbird-ai-gateway.service` if explicitly authorized for that implementation step, verify loopback listeners/health/tools/authorization/Relay read-only posture, and preserve rollback evidence. Record signed/end-to-end chat acceptance separately after live validation.

## Safety boundary

Do not expose secret values or raw protected evidence. Do not change authentication policy, credentials, DNS, firewall, certificates, public listeners, Relay/SQLite data, upstream posting, federation, telephony routing or production traffic as part of Private AI retrieval hardening. Retrieved content never grants scopes or write authority.
