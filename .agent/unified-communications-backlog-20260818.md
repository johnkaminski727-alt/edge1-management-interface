# Unified Communications — Remaining Backlog

Date: 2026-08-18

This backlog contains only work not completed by the safe repository-side convergence pass.

## Runtime verification

- [ ] Run a fresh authenticated read-only Edge1 acceptance pass using the approved Edge1 Live Shell connector.
- [ ] Confirm deployed revisions/service versions for Communications workspace, Messaging Gateway, Mail Room AI adapter, Private AI gateway, Voice/SIP, and Communications Relay.
- [ ] Confirm loopback listeners and any existing authenticated reverse-proxy mapping without changing firewall, DNS, certificates, or authentication policy.
- [ ] Confirm the authoritative canonical communications-event snapshot/feed source used by the workspace.
- [ ] Record live rollback/checkpoint evidence for already-deployed components.

## Mail correspondence

- [ ] Identify and explicitly authorize the authoritative native Mail Room correspondence/thread source for `mail.correspondence.read`.
- [ ] Build a sanitized bounded adapter that preserves native IDs, thread relationships, authorization boundaries, and provenance.
- [ ] Validate that outbound audit metadata is never substituted for correspondence bodies/history.

## MMS quarantine runtime

- [ ] Attach private quarantine storage with bounded retention and access policy.
- [ ] Attach a trusted malware/media scanner behind the fail-closed scanner callback boundary.
- [ ] Add operational readiness/health evidence for storage and scanner degradation.
- [ ] Design a separately authorized, audited release workflow; do not grant release to Private AI.

## Provider / production activation

These remain outside standing safe repository authority and require separate explicit approval where applicable:

- [ ] provider credentials/configuration;
- [ ] live SMS/MMS routing and transmission;
- [ ] live mail transmission where not separately authorized;
- [ ] SIP/carrier route or dialplan mutation;
- [ ] production call origination;
- [ ] emergency calling changes;
- [ ] number porting;
- [ ] STIR/SHAKEN changes;
- [ ] DNS/firewall/certificate/authentication-policy changes;
- [ ] quarantine release;
- [ ] provider contractual or financial actions.

## Product follow-through

- [ ] Populate evidence-backed cross-channel identity links only when authoritative evidence exists.
- [ ] Replace snapshot-style workspace event input with an approved bounded runtime aggregation feed if/when the native channel adapters are deployed.
- [ ] Run accessibility/browser acceptance on the deployed Communications workspace.

No item above should be represented as complete until evidence exists for that specific layer.
