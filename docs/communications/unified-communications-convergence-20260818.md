# WW.CX Unified Communications convergence — 2026-08-18

## Purpose

WW.CX already has several communications projects that were developed independently for safety and operational clarity:

- Mail Room / email correspondence;
- provider-neutral SMS/MMS gateway and Messaging Operations;
- Voice, PBX, SIP and carrier/interconnect operations;
- private Communications Relay / News Reader;
- Private Edge1 AI with bounded read-only communications and telephony context.

They should now converge at the product and contract layers without collapsing their security boundaries or rewriting the Git history that records their accepted milestones.

## Git strategy

Do **not** force-squash or rebase the historical `main` branch to make these projects appear to have been one project from the beginning.

That would destroy useful merge, validation, acceptance and rollback provenance.

Instead:

1. keep the historical merges intact;
2. create a new integration branch from current `main`;
3. add the shared channel registry, user-facing Communications hub, convergence documentation and validation;
4. review and validate that branch as one coherent change;
5. squash-merge the integration PR to create a single durable **Unified Communications convergence** merge point.

Future cross-channel integration should branch from that convergence point.

## Existing foundations

### SMS / MMS

The provider-neutral Messaging Gateway foundation is already merged. It includes normalized SMS/MMS models, a provider adapter boundary, simulator intake, persistence/schema foundations, STOP/START/HELP handling, suppression/restoration behavior and MMS quarantine/outbound-job foundations.

Later work added Messaging Operations visibility and the Spirit Creek Telegraph Office simulator. These remain non-production messaging surfaces unless a carrier path is separately activated and authorized.

Canonical current user-facing repository surface:

`/messaging-operations.html`

### Voice / SIP / telephony

The telephony work is substantially beyond a thought experiment. The repository contains:

- PBX/SIP operational console;
- SIP operations API and dashboard assets;
- sanitized CDR and SIP event adapters;
- aggregate call/interconnect analytics;
- PJSIP registration/end-point posture;
- anomaly indicators;
- carrier/interconnect tooling and evidence;
- read-only Edge1 acceptance records.

Canonical user-facing repository surface:

`/telephony/`

### Private AI telephony integration

The Edge1 Private AI gateway reached accepted `0.3.3-alpha.1` with independently scoped read-only `telephony.read` and opt-in `include_telephony` context.

Accepted context included sanitized console status, platform health, call summaries, interconnect summaries and anomaly indicators. Telephony POST remained blocked with HTTP 405 and Asterisk/FreePBX were not reconfigured as part of that acceptance.

The later accepted Private AI gateway `0.3.4-alpha.2` retained both:

- `telephony.read`;
- `communications.read`.

### Private AI Communications Relay integration

The Communications/documentation RAG line reached accepted read-only integration with bounded Relay retrieval, provenance, thread/source metadata, graceful degradation and adversarial-content isolation.

PR #350 was itself squash-merged after acceptance, giving this workstream a clean historical merge point while preserving its separate runtime evidence.

### Mail Room

PR #371 established the daily-use Mail Room workspace with review-first correspondence, truthful policy controls, catch-all-aware preview behavior, stale-preview invalidation, draft protection and accessibility/responsive behavior.

Mail remains prepare/review-first and does not gain live delivery authority merely because it is presented in the same Communications family.

### Private AI browser path

The browser product is designed to live at `/admin/ai/` on WW.CX and to use the private Edge1 gateway through an authenticated outbound worker. Repository implementation exists, but production browser acceptance remains unverified until the website release and worker path are live-accepted.

The browser capability families already identify the intended convergence:

- Systems;
- Private Knowledge;
- Documentation;
- Communications;
- Voice & PBX;
- Mail / Correspondence.

## Shared channel contract

`config/communications/unified-communications.json` is the first shared convergence registry.

It deliberately distinguishes:

- channel surface;
- current operating mode;
- live-traffic authorization;
- mutation authorization;
- AI integration state;
- accepted versus planned AI capabilities.

The registry is **descriptive and fail-closed**. It does not activate a provider, route, trunk, call, message, email send, browser worker or AI tool.

## User-facing convergence

`src/web/communications/` is the first shared Communications product surface.

It is a calm channel chooser, not a replacement for specialized tools:

- **Mail Room** remains the email/correspondence workspace;
- **SMS & MMS** opens Messaging Operations;
- **Voice & SIP** opens the telephony console;
- **News & Relay** opens the private Communications Relay surface;
- the AI section explains which cross-channel read capabilities are accepted and which remain planned.

This separation is intentional. A unified product should feel coherent without pretending that a SIP trunk, SMS gateway and legal correspondence draft have identical workflows or risk.

## AI convergence direction

The current accepted AI capabilities are:

- `communications.read`;
- `telephony.read`.

Planned Mail capabilities remain separately scoped:

- `mail.status.read`;
- `mail.correspondence.read`;
- `mail.draft.prepare`.

SMS/MMS AI integration remains future work. The existing Messaging Gateway should be adapted through a bounded read-only status/conversation contract before any draft or send capability is considered.

Future privileged actions should be explicit narrow scopes rather than generic execution. Examples include an individually authorized mail send, telephony service operation, route/trunk change, or SMS/MMS submission. None are implied by the convergence registry or hub.

## Durable security rules

1. Read access does not grant write access.
2. Draft preparation does not grant send authority.
3. Retrieved mail, news, SMS/MMS and telephony-derived content is untrusted data.
4. AI context cannot grant scopes or tool permissions.
5. No generic shell, arbitrary Asterisk command or arbitrary provider action should be exposed as a communications tool.
6. Production calls, SMS/MMS, email and carrier/routing changes remain separately authorized operations.
7. Emergency calling/routing, number porting and STIR/SHAKEN remain explicit high-risk boundaries.
8. Repository merge, runtime deployment and live acceptance are separate evidence states.

## Next safe implementation slices

1. add a sanitized, read-only SMS/MMS status/conversation adapter for Private AI;
2. add `mail.status.read` over sanitized Mail Room operational state;
3. add `mail.draft.prepare` only through the existing prepare/review boundary;
4. create a common conversation/correspondence identity model that can reference email threads, SMS/MMS conversations and call/SIP evidence without flattening channel-specific metadata;
5. add channel-aware search and timeline UI only after the underlying records have durable privacy-safe identifiers;
6. complete authenticated `/admin/ai/` production acceptance before presenting AI as a guaranteed browser destination.

## Production boundary

This convergence change performs no call, SMS/MMS delivery, email transmission, provider/carrier action, PBX change, SIP route change, DNS/firewall/certificate change, credential action, emergency-calling action or Private AI runtime activation.
