# Mail Room catch-all outbound identity handoff — 2026-08-18

## Baseline

- Repository: `johnkaminski727-alt/edge1-management-interface`
- PR #362 was confirmed merged before this work began.
- PR #362 known head `c278ae3d8013218a4f005d047d8691a3b6403a76` had all four recorded validations green.
- Current `main` at branch creation: `dad71ef3abf993cd2ad785586f1d608b0b4c4d0c`.
- Working branch: `agent/mail-room-catchall-outbound-identity-20260818`.

## Gap addressed

The inbound Mail Room supports managed-domain catch-all routing, but the no-send outbound preparation path previously rejected an `original_recipient` that was not already listed in `recipient_to_sender`.

That prevented a reply to an inbound catch-all identity such as `invoices@creekco.ca` from preserving the correspondence identity.

## Implemented behavior

`server/identity_aware_outbound_gateway.py` now:

- recognizes an unseen `original_recipient` when its domain is present in the configuration-driven managed-domain identity registry;
- creates an in-memory preparation-only mapping so the existing canonical resolver can preserve the exact address;
- marks the result with `original_recipient_catch_all_proposal`;
- forces the proposal to `live_enabled = false`;
- adds a `live_delivery_block_reason` to prepared request metadata;
- rejects internal-only delivery mailboxes and the reserved system sender as catch-all public identities;
- leaves unmanaged-domain behavior fail-closed;
- keeps submitted sender headers non-authoritative;
- leaves committed live sender authorization unchanged.

`tests/validate_outbound_mail_prepare_cli.py` now exercises the managed catch-all proposal, unmanaged-domain rejection, and internal-only identity rejection.

Documentation: `docs/messaging-operations/catch-all-outbound-identity-proposals-20260818.md`.

## Production boundary

No live provider, DNS, MX, SPF, DKIM, DMARC, credentials, mailbox provisioning, routing cutover, automatic sending, destructive mail handling, or legal disclaimer content was changed.

A proposed catch-all identity remains preparation-only until it is separately registered and provider/domain-authorized through an approved production process.

## Next safe repository work

After this PR is green and merged, continue with the next smallest Mail Room gap. Priority candidates are thread/correspondence correlation metadata and policy-scoped automatic-reply gating, while preserving disabled-by-default transmission and the established threat-policy boundary.
