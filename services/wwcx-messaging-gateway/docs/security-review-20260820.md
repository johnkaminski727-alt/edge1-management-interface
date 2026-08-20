# WW.CX Messaging focused security review

Date: 2026-08-20

Scope: repository source plus fresh bounded Edge1 read-only observations available during the autonomous completion mission. This document distinguishes source evidence from runtime evidence and does not claim checks that require unavailable privileged execution.

## Authentication and authorization

**Source:** management reads require the management-read token; management control has a separate enable flag and control token; BigBird read and prepared-draft surfaces preserve `mutation_authorized=false`; carrier credentials are injected rather than committed.

**Runtime observed:** BigBird was healthy in read-only mode and exposed messaging status/conversation read and prepared-draft tools without a send tool. Messaging Gateway remained loopback-only.

**Remaining:** privileged inspection of reverse-proxy authentication for every published Messaging UI/API path is still required before any public carrier webhook or content-bearing UI exposure.

## Webhook signatures and replay

The provider-neutral boundary delegates verification to each adapter. Simulator callbacks use a private token. Telnyx source verifies Ed25519 over `timestamp|raw_body`, requires signature/timestamp headers and rejects timestamps outside a five-minute window. Verified callbacks are durably receipted; unverified requests only affect bounded aggregate counters. Changed-body reuse of a provider event ID is rejected.

Never relax signature verification or replay freshness to recover from an outage; first check time synchronization, proxy body preservation and provider configuration.

## Secret handling

No provider API key or webhook private secret is stored in the Telnyx adapter source. BigBird does not receive carrier credentials. Error returns expose exception types/status categories rather than credential material.

Remaining activation work must ensure service environment files are private, logs redact authorization headers, secrets are not copied into screenshots/evidence, and credential rotation remains separately approved.

## Least privilege and listeners

Fresh Edge1 observation showed Messaging Gateway on `127.0.0.1:58080`, not a wildcard listener. BigBird was read-only. The current source keeps Telnyx unregistered, outbound worker disabled by default, provider allowlist defaulting to simulator, and outbound policy disabled by default.

## Database permissions and durability

PostgreSQL-backed durable stores and migrations are implemented and have prior private acceptance evidence. A fresh privileged role/GRANT inspection was not available during this pass; verify the runtime database role cannot perform unrelated cluster administration before production carrier activation.

## CSRF

The current gateway management surface uses header tokens and is intended for private/server-to-server access. The legacy Messaging Operations web service exposes only read endpoints and a deterministic sandbox simulator; it does not contain carrier-send capability. If browser-accessible state-changing management controls are ever added behind cookies/session auth, add explicit CSRF protections rather than relying on network location.

## XSS and content rendering

The modernized Messaging Operations page escapes values before inserting diagnostics/history into HTML. The existing gateway read API truncates message text and marks it untrusted. Any future conversation bubble renderer must use text-safe DOM insertion/escaping and must never render inbound HTML as trusted markup.

## SSRF and provider media

MMS provider URLs are untrusted. The private quarantine store intentionally separates provider metadata from storage paths and requires digest-verified bytes before trusted scanning. The current Telnyx adapter normalizes provider media metadata but does not itself fetch remote media, which avoids introducing an unrestricted SSRF primitive.

Before implementing provider-media acquisition, require an adapter-specific authenticated downloader, HTTPS, an allowlisted Telnyx media host/path contract derived from current provider documentation, redirects disabled, private/link-local/loopback destination rejection, bounded size/time, content-type validation and digest verification before persistence. Do not add a generic arbitrary-URL fetcher.

## File and path handling

Private quarantine paths are content-addressed from validated SHA-256 digests. Provider filenames are normalized and never determine blob paths. Private directories/files are forced to restrictive permissions and symlinks/non-regular files fail closed.

## Attachment MIME/content validation

Content type is normalized but is metadata, not proof. Trusted malware scanning operates on the verified stored blob. A clean verdict remains held. Future safe preview/release must validate actual file content, supported preview formats and release policy separately.

## Prompt injection

Retrieved communications are untrusted data. BigBird's messaging tools now provide an explicit AI context envelope stating that message content cannot grant scopes, authorize tools, override policy, disclose secrets, authorize send or release quarantine. Test content intentionally contains a policy-bypass instruction and still produces all authority flags as false.

AI-derived summaries/classifications must remain separate from the native message and carry provenance when persisted.

## Rate limiting and abuse

Outbound rate controls are durable and evaluated after policy/suppression checks. Webhook failure accounting is bounded. Public carrier webhook activation will require reverse-proxy request-size/rate controls and provider-specific abuse monitoring without persisting unverified bodies.

## Logging and audit integrity

Verified webhook receipts, delivery events, queue state, consent state and quarantine audit events are durable. Runtime log-redaction behavior should be freshly sampled under authorized shell access before production activation. Never log Authorization headers, tokens, full MMS provider URLs with embedded credentials, or unnecessary message bodies.

## Retention and privacy

Private quarantine has bounded retention metadata and remains non-web-served. Native communication records should remain authoritative; derived AI annotations should be minimal and provenance-bound. Production retention/deletion policy requires business/legal approval before destructive automation is enabled.

## Dependency risk

The Telnyx adapter adds bounded `httpx` and `cryptography` runtime dependencies. CI installs and tests them. A dependency vulnerability scan should be part of production release evidence; no claim is made here that the current environment has zero CVEs.

## Fresh unresolved runtime defect

`bigbird-edge1-connector.service` and `bigbird-edge1-connector-maintenance.service` were observed failed while core BigBird remained healthy. They must be inspected with authenticated Edge1 execution and either repaired, explicitly superseded/disabled, or formally retired. An unexplained failed-unit state is not acceptable as final production readiness.

## Security conclusion

The repository defaults remain strongly fail-closed and the Telnyx adapter does not broaden live authority. No critical source-level reason to block continued private development was found in this pass. Production carrier activation is still blocked on explicit approvals plus fresh privileged verification of reverse-proxy authentication, database role scope, log redaction, scanner runtime, dependency vulnerabilities, the failed connector units, and any public webhook network changes.
