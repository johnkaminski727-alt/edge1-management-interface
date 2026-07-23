# WW.CX Accessible Telegraph and Carrier Integration

## Objective

Build a standards-based communications subsystem that combines secure messaging, telegraph federation, real-time text, legacy TTY interworking, carrier routing, and accessible operator tooling without overstating encryption or regulatory status.

## System boundary

The project is one coordinated program with four principal components:

1. **Carrier Core** — SIP trunks, numbering, call routing, identity, billing hooks, codec policy, relay routing, and emergency-routing boundaries.
2. **Telegraph Network Office** — authenticated store-and-forward messaging, office-to-office federation, signed receipts, audit events, and encrypted envelope transport.
3. **Accessible Media Gateway** — RFC 4103/T.140 real-time text, legacy Baudot TTY interworking, VCO/HCO support, and controlled relay integration.
4. **Unified Administration Centre** — configuration, health, peer status, media negotiation evidence, accessibility diagnostics, and claim-state reporting.

## Security principles

- End-to-end encryption is asserted only when plaintext and endpoint private keys remain unavailable to WW.CX, carriers, offices, gateways, and relay operators.
- Mutual TLS protects office-to-office transport but does not by itself establish end-to-end encryption.
- Legacy TTY conversion, human relay, server-side transformation, content moderation, and plaintext archival are explicit downgrade boundaries.
- Every delivered session exposes a machine-readable security state and downgrade reason.
- Audit records contain identifiers, timestamps, routing state, cryptographic evidence, and delivery status, but not message plaintext.

## Accessibility principles

- RTT is the preferred native text conversation mode.
- TTY is retained as an interoperability mode, not treated as equivalent to modern RTT.
- Accessible operation must not depend solely on sound, colour, pointer precision, or rapid timed interaction.
- VCO, HCO, screen-reader operation, keyboard operation, visual alerts, and transcript controls are first-class requirements.

## Peering model

Initial federation uses authenticated application-layer peering over ordinary IP connectivity. Each office exchanges signed envelopes through mutually authenticated TLS. The underlying Internet, private WAN, or future transport is replaceable and is not part of the end-to-end trust claim.

## Delivery stages

1. Architecture, schemas, validators, and explicit safety gates.
2. Local two-endpoint encrypted message proof.
3. Two isolated Telegraph Office peers with signed delivery receipts.
4. Accessible browser client and administration status.
5. Asterisk test integration and RTT negotiation.
6. Legacy TTY laboratory gateway and downgrade disclosure.
7. Carrier staging integration.
8. Separately approved production routing, relay activation, and emergency validation.

## Approval boundaries

Repository work, simulation, test fixtures, isolated laboratory services, documentation, and reversible staging are authorized. Credentials, contracts, payments, live carrier traffic, emergency calls, number porting, production routing, STIR/SHAKEN signing, and unverified compliance declarations remain separately gated.
