# Edge1 Private AI Chat Communications and RAG Live Acceptance

Accepted: 2026-08-17 03:33 UTC

- Service: `bigbird-ai-gateway.service`.
- Runtime: `/opt/bigbird-ai-gateway/app`.
- Version: `0.3.2-alpha.1`.
- Listener: `127.0.0.1:8787`.
- Mode: read-only.
- Added scoped `communications.read` capability.
- Relay source: loopback read-only API at `127.0.0.1:8100`.
- Documentation RAG uses the existing internal `operations` FTS5 collection.
- Requests may opt into `include_communications` and `include_documentation`.
- Retrieved documents and articles remain untrusted, secret-filtered and context-bounded.
- Document and Relay provenance use `[S#]` and `[C#]` markers.
- Relay POST remained blocked with HTTP 405.
- Gateway and Relay services remained active.
- Listeners remained loopback-only.
- Library integrity remained `ok`: 63 documents and 501 chunks.
- No Relay/database mutation, public exposure, DNS, firewall, certificate, credential or federation change occurred.
- Runtime backup: `/var/backups/bigbird-ai-gateway-comms-rag-20260817T033259Z`.

Remaining work: signed end-to-end chat acceptance, richer source/thread provenance, graceful Relay degradation, prompt-injection fixtures, and source-controlled regression tests.
