# Mail Room catch-all outbound identity proposals — 2026-08-18

## Purpose

The Mail Room accepts inbound mail for arbitrary valid local-parts on managed domains. The exact original envelope recipient is therefore a meaningful correspondence identity even when that address has never been pre-registered as an outbound sender.

This repository increment preserves that identity during **no-send preparation** without granting it delivery authority.

## Selection behavior

For reply preparation, sender selection remains server-side and authoritative:

1. system-generated mail uses the reserved system sender;
2. a registered `original_recipient` uses its configured sender mapping;
3. an unregistered `original_recipient` at a managed domain becomes a catch-all outbound identity proposal;
4. otherwise the existing identity-hint/default rules apply.

A catch-all proposal uses the exact normalized original recipient as `from_address` and `reply_to`, records `sender_selection.reason = original_recipient_catch_all_proposal`, and remains `live_enabled = false`.

The prepared artifact also records `live_delivery_block_reason` explaining that the identity is proposed only and is not provider-authorized for live delivery.

## Safety boundaries

This change does not activate delivery and does not modify provider or DNS state.

- `outbound_activation_authorized` remains unchanged.
- The committed live sender allow-list remains authoritative.
- A proposed catch-all address is not inserted into the committed identity registry or live allow-list.
- The live-send facade rejects a proposal even if an operator attempts to use the delivery path.
- Unmanaged-domain recipients remain rejected.
- Internal delivery identities such as `maildesk@ww.cx` and `john-inbox@ww.cx` cannot become public catch-all sender proposals.
- The reserved `noreply@ww.cx` identity cannot be obtained through catch-all reply selection.
- Submitted `From:` and `Reply-To:` values remain untrusted; the server-side selection result replaces them.

## Example

Inbound envelope recipient:

```text
invoices@creekco.ca
```

If that address is not yet registered as an outbound sender, reply preparation may produce:

```text
status: prepared_not_sent
from_address: invoices@creekco.ca
reply_to: invoices@creekco.ca
sender_selection.reason: original_recipient_catch_all_proposal
sender_selection.live_enabled: false
```

No provider submission is attempted.

## Validation

`tests/validate_outbound_mail_prepare_cli.py` covers:

- registered original-recipient identity selection;
- unseen managed-domain catch-all proposal preparation;
- forced non-live status for the proposal;
- explicit delivery-block explanation;
- rejection of unmanaged-domain original recipients;
- rejection of internal-only delivery identities;
- existing system-sender and submitted-From protections.

## Deferred work

Provider authorization and promotion of a proposed identity to a live sender remain separate privileged operations. Production outbound sending, provider provisioning, DNS/MX/SPF/DKIM/DMARC changes, and live routing cutover are not part of this increment.
