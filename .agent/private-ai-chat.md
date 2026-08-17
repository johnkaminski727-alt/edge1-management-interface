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

Draft PR #349 establishes the living Communications permission/regression contract and repository-owned validator:

- `docs/communications/edge1-private-ai-chat-communications-permissions-and-regression-contract.md`;
- `tests/validate_private_ai_gateway_contract.py`.

The validator distinguishes the dot-form tool name `communications.read` from the colon-form authorization scope `communications:read` and checks the accepted read-only gateway contract: explicit opt-in, authorization gate, bounds, secret filtering, untrusted-content marker, Relay failure handling, provenance response, loopback-only default, GET-only Relay requests and absence of write-capable Relay client methods.

Current PR head at this reconciliation point: `7baeafc18a90bdda11264a83958fb84e49abee0f`.

CI on that head:

- `Validate repository` run 1281: PASS;
- `Edge1 Operator Validation` run 1113: PASS;
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

## Remaining work

Safe repository work:

1. prepare richer source/thread provenance preservation in the gateway adapter;
2. add representative prompt-injection article fixtures and regression assertions;
3. prepare graceful Communications Relay degradation so a Relay outage does not fabricate data or broaden permissions;
4. keep all Relay-facing gateway methods GET-only and bounded;
5. preserve telephony integration while advancing the gateway beyond `0.3.3-alpha.1`.

Live work pending an authenticated Edge1 execution path:

1. run `python3 tests/validate_private_ai_gateway_contract.py --gateway-root /opt/bigbird-ai-gateway/app` against the deployed source tree;
2. inspect the exact current source/working state before any gateway patch;
3. validate any staged upgrade against the actual current runtime source;
4. if explicitly proceeding with a live gateway change, back up first, apply the smallest change, restart only the gateway service, verify loopback listeners/health/tools, and preserve rollback evidence;
5. record signed/end-to-end chat acceptance separately after live validation.

## Safety boundary

Do not expose secret values or raw protected evidence. Do not change authentication policy, credentials, DNS, firewall, certificates, public listeners, Relay/SQLite data, upstream posting, federation, telephony routing or production traffic as part of Private AI retrieval hardening. Retrieved content never grants scopes or write authority.
