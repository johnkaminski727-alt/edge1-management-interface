# WW.CX Messaging carrier adapter decision

Date: 2026-08-20

## Decision

Use **Telnyx as the first technically complete real-carrier adapter target** for the WW.CX Messaging Gateway, while keeping commercial carrier activation unapproved and the runtime provider registry simulator-only.

This is an engineering/reference-adapter decision, not contractual acceptance, purchasing authority, DID assignment or authorization for live traffic.

## Dual-carrier follow-on decision

After the first Telnyx adapter was completed, the carrier strategy was expanded to keep **both Telnyx and Bandwidth as first-class WW.CX carrier adapters** rather than forcing a single-provider dependency.

The resulting operating model is deliberately provider-neutral:

- a telephone number/sender remains explicitly associated with its owning/configured provider;
- Telnyx and Bandwidth may be enabled independently after their separate activation gates are satisfied;
- routing policy may choose a provider before submission based on the number binding and later operational policy;
- a failed or outcome-uncertain send is **not** transparently retransmitted through the other carrier, because that can violate sender ownership and create duplicate messages;
- provider health may inform routing for future eligible traffic, but it does not override number ownership, consent, registration, compliance, or idempotency controls;
- carrier-specific credentials and callback authentication remain isolated behind each adapter.

The repository therefore treats Telnyx and Bandwidth as upstream resources behind WW.CX's communications control plane, not as architecture-defining dependencies.

## Why Telnyx for the first adapter

Current official provider documentation was rechecked before implementation. Telnyx provides a clean fit for the existing WW.CX carrier-neutral boundaries:

- Ed25519 webhook signing with timestamped replay protection over the raw callback body;
- SMS and MMS messaging APIs;
- inbound `message.received` callbacks;
- terminal `message.finalized` delivery callbacks;
- authenticated provider-media retrieval for MMS;
- Canadian and United States messaging/number capability relevant to expected WW.CX use;
- a provider message identifier suitable for durable DLR reconciliation;
- an API model that can be wrapped without exposing provider credentials to BigBird.

Bandwidth is now the second implemented adapter. Its materially different callback/authentication behavior validates the provider-neutral design: Messaging-V2 callbacks are JSON arrays, optional callback credentials use HTTP Basic authentication with an RFC-style `401` challenge, outbound submission uses the Bandwidth Messaging-V2 API with Basic API credentials, and terminal delivery events use Bandwidth-specific callback types.

Twilio remains a credible interoperability/reference option with mature request-signature validation and broad messaging support, but no repository evidence requires adding it to the first dual-carrier implementation.

## Pricing and regulatory caution

Provider pricing, carrier surcharges, number costs, 10DLC/toll-free registration requirements, Canadian/US regulatory requirements, messaging profiles and deliverability terms can change. They must be revalidated at the moment procurement/activation is proposed. No price in documentation should be treated as a standing purchasing commitment.

## Implemented source boundary

The Telnyx adapter covers:

- credential-injected configuration only;
- Ed25519 signature validation;
- five-minute timestamp freshness check;
- inbound SMS normalization;
- inbound MMS metadata normalization;
- terminal DLR mapping;
- outbound SMS/MMS request formation;
- provider message ID capture;
- explicit permanent-rejection handling;
- safe pre-submit connection retry classification;
- conservative outcome-uncertain handling for timeouts/server ambiguity.

The Bandwidth adapter covers:

- credential-injected configuration only;
- callback HTTP Basic verification with constant-time credential comparison;
- provider-specific `WWW-Authenticate` challenge metadata;
- single-event JSON-array callback normalization, rejecting multi-event batches rather than silently dropping events;
- inbound SMS and MMS metadata normalization;
- allowlisted Bandwidth media-origin validation while leaving undigested MMS media held by the existing fail-closed quarantine policy;
- terminal `message-delivered` and `message-failed` DLR mapping;
- Messaging-V2 outbound SMS/MMS request formation;
- Bandwidth's ten-recipient outbound limit enforced before submission;
- provider message ID capture;
- explicit permanent-rejection handling;
- safe retry for Bandwidth-confirmed no-send `429` and `5xx` HTTP responses;
- conservative outcome-uncertain handling for transport/read/write ambiguity where provider acceptance cannot be proven either way.

Both adapters are tested with provider-specific authentication, inbound normalization, delivery callbacks, outbound request formation, rejection handling, safe-retry behavior and outcome-uncertain failure behavior.

## Deliberately not activated

`build_provider_registry()` still returns only the simulator. Neither Telnyx nor Bandwidth becomes active merely because its source exists or passes CI.

The following remain explicit approval boundaries:

- provider account/contract acceptance or charges;
- API credentials or private activation links;
- messaging profile/application creation where externally consequential;
- buying or assigning telephone numbers/DIDs;
- public webhook DNS/firewall/certificate/reverse-proxy changes;
- live inbound or outbound SMS/MMS test traffic;
- production traffic cutover;
- credential rotation;
- legal or regulatory representations.

## Activation sequence after approval

When activation is eventually approved, preserve this order separately for each provider: verify the provider account and regulatory prerequisites; create/retrieve credentials outside Git; assign the intended number/DID and record its provider binding; configure the adapter privately but leave workers disabled; validate provider authentication in private/sandbox conditions; prepare rollback; apply the separately approved public webhook reachability changes; accept one bounded inbound canary; accept one bounded outbound canary with explicit operator confirmation; verify DLR, consent/suppression, audit, monitoring and rollback; only then consider broader traffic.

Do not configure cross-carrier automatic retransmission as part of activation. Any future failover policy must prove that the alternate provider is authorized for the sender identity and that the original outcome is known not to have been accepted before another submission is permitted.
