# WW.CX Messaging carrier adapter decision

Date: 2026-08-20

## Decision

Use **Telnyx as the first technically complete real-carrier adapter target** for the WW.CX Messaging Gateway, while keeping commercial carrier activation unapproved and the runtime provider registry simulator-only.

This is an engineering/reference-adapter decision, not contractual acceptance, purchasing authority, DID assignment or authorization for live traffic.

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

Bandwidth remains a credible alternative and should remain architecturally possible. Its messaging callback/authentication model and API semantics differ enough that the existing provider-neutral interface continues to be valuable. Twilio remains a credible interoperability/reference option with mature request-signature validation and broad messaging support, but no repository evidence required choosing it over the current Telnyx adapter target.

## Pricing and regulatory caution

Provider pricing, carrier surcharges, number costs, 10DLC/toll-free registration requirements, Canadian/US regulatory requirements, messaging profiles and deliverability terms can change. They must be revalidated at the moment procurement/activation is proposed. No price in documentation should be treated as a standing purchasing commitment.

## Implemented source boundary

The Telnyx adapter now covers:

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

Tests exercise valid/tampered/stale signatures, inbound SMS/MMS, terminal delivery status, missing credentials, accepted sends, explicit 4xx rejection, proven connection failure, read timeout and server-error uncertainty.

## Deliberately not activated

`build_provider_registry()` still returns only the simulator. The Telnyx adapter source does not become active merely because it exists or passes CI.

The following remain explicit approval boundaries:

- provider account/contract acceptance or charges;
- API credentials or private activation links;
- messaging profile creation where externally consequential;
- buying or assigning telephone numbers/DIDs;
- public webhook DNS/firewall/certificate/reverse-proxy changes;
- live inbound or outbound SMS/MMS test traffic;
- production traffic cutover;
- credential rotation;
- legal or regulatory representations.

## Activation sequence after approval

When approval is eventually granted, preserve this order: verify provider account and regulatory prerequisites; create/retrieve credentials outside Git; assign the intended number/DID; configure the adapter privately but leave workers disabled; validate provider authentication and webhook signatures in sandbox/private conditions; prepare rollback; apply the separately approved public webhook reachability changes; accept one bounded inbound canary; accept one bounded outbound canary with explicit operator confirmation; verify DLR, consent/suppression, audit, monitoring and rollback; only then consider broader traffic.
