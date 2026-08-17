# Edge1 Private AI Chat Communications 0.3.4 Live Acceptance

Accepted: 2026-08-17 06:20 UTC  
System: `edge1.ww.cx`

## Accepted runtime state

- Service: `bigbird-ai-gateway.service`.
- Runtime source: `/opt/bigbird-ai-gateway/app`.
- Runtime Python: `/usr/bin/python3.11` (`Python 3.11.2`).
- Service identity: `bigbird-ai:bigbird-ai`.
- Version: `0.3.4-alpha.1`.
- Listener: `127.0.0.1:8787` only.
- Mode: read-only.
- Library integrity: `ok`.
- Library state at acceptance: 63 indexed documents, 501 chunks, zero rejected documents.
- Tool count at health acceptance: 6.

## Accepted communications behavior

The deployed `0.3.4-alpha.1` source passed the repository-owned candidate/live contract validator after installation and after service restart.

Accepted contract checks:

- explicit Communications opt-in and `communications.read` authorization path preserved;
- caller authorization scope remains `communications:read` and distinct from the tool name;
- telephony read integration remains present and independently scoped;
- Communications Relay failures now degrade with a bounded system-generated `communications_warning` rather than the legacy Communications-specific hard HTTP 502;
- degraded Communications retrieval returns no fabricated Communications articles;
- retrieved Communications content and provenance remain explicitly untrusted;
- source, source-item, ingest, thread and selected upstream provenance are carried into Communications source metadata/context;
- Communications Relay adapter remains loopback-only, bounded and GET-only;
- no POST/PUT/PATCH/DELETE, SQLite, subprocess or equivalent write/escape capability was introduced into the AI-facing Communications Relay adapter.

## Live validation evidence

The guarded activation completed with:

```text
ACTIVATION=PASS
version=0.3.4-alpha.1
runtime=/usr/bin/python3.11
mode=read-only
listener=127.0.0.1:8787
relay_write_boundary=HTTP_405
rollback_backup=/var/backups/bigbird-ai-gateway-comms-0.3.4-20260817T062020Z
```

Additional observed acceptance evidence:

- candidate compiled successfully using the actual gateway runtime Python;
- complete staged/shadow source passed the `0.3.4` contract validator;
- installed live source passed the same validator before restart;
- `bigbird-ai-gateway.service` stopped cleanly and restarted cleanly;
- post-restart health returned `ok=true`, `enabled=true`, `version=0.3.4-alpha.1`, `mode=read-only` and library integrity `ok`;
- live source passed the `0.3.4` contract validator again after restart;
- `127.0.0.1:8787` remained the gateway listener with no wildcard/public bind;
- a live POST attempt to the Communications Relay status endpoint returned HTTP 405, preserving the Relay write boundary;
- no DNS, firewall, certificate, authentication-policy, credential, Relay database, NNTP federation, posting, moderation or public-exposure change was made.

## Rollback point

Protected runtime rollback backup:

```text
/var/backups/bigbird-ai-gateway-comms-0.3.4-20260817T062020Z
```

Two earlier guarded attempts did not become accepted deployments: one rolled back after a guessed runtime-Python path proved incorrect, and one stopped before installation when the service account could not traverse the operator-private staging directory. Both failure modes were corrected without weakening the staging-directory permission boundary.

## Source-control evidence

- Permission/regression foundation: PR #349, merged to `main` as `900f85a31d69ec0cbddde4f0387eb660922275f7`.
- `0.3.4` preparation/validator branch: PR #350.
- PR #350 repository validation and Edge1 Operator Validation were green before the accepted activation.
- The dedicated live validator is `tests/validate_private_ai_comms_candidate_contract.py`.

## Remaining acceptance work

The runtime activation is accepted. The following end-to-end chat behaviors still require separate evidence before the Communications integration can be considered fully closed:

1. ordinary chat without Communications opt-in returns no Communications context;
2. Communications opt-in without `communications:read` fails closed with no Communications material;
3. authorized Communications opt-in succeeds read-only and returns Communications provenance;
4. an adversarial/prompt-injection article remains inert as retrieved data;
5. a controlled Communications Relay failure demonstrates graceful chat degradation with `communications_warning`, no fabricated Communications results and no retry/mutation behavior;
6. signed/durable end-to-end chat acceptance is recorded.

Until those checks are recorded, PR #350 should remain unmerged/draft even though the live `0.3.4-alpha.1` runtime itself is accepted.
