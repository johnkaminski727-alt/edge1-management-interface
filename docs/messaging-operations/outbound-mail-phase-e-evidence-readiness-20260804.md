# Outbound mail Phase E accepted-evidence readiness

Date: 2026-08-04

## Objective

Reconcile the accepted WW.CX provider, public DNS, and DKIM records into the outbound-mail Phase E readiness model without repeating network queries, reading credentials, changing runtime configuration, activating a provider or sender, or sending a message.

The evidence-aware report is generated with:

```sh
python3 tools/messaging/outbound_mail_phase_e_evidence.py \
  --pretty \
  --require-safe-disabled \
  --output /tmp/outbound-mail-phase-e-evidence.json
```

## Accepted evidence

The report consumes only committed read-only records:

- `records/messaging/provider-inventories/namecheap-private-email-wwcx-20260802.json`;
- `records/messaging/dns-inventories/mail-domain-dns-acceptance-20260804.json`;
- `records/messaging/dns-inventories/wwcx-dkim-dns-acceptance-20260804.json`;
- the committed gateway, policy, and sender-identity configuration.

Accepted facts now include:

- WW.CX uses Namecheap Private Email in public MX evidence;
- provider-visible active mailboxes are `blank@ww.cx` and `domaincontact@ww.cx`;
- no provider-visible aliases were reported;
- Catch-All forwards to `blank@ww.cx`;
- provider-side routing remains unknown;
- `john-inbox@ww.cx`, `maildesk@ww.cx`, and `john@ww.cx` are not observed as provider objects;
- WW.CX publishes the accepted Namecheap Private Email SPF record;
- WW.CX publishes no DMARC record in the accepted DNS evidence;
- `default._domainkey.ww.cx` publishes a valid-shape RSA DKIM record with resolver consensus;
- `privateemail._domainkey.ww.cx` was not observed.

## Refined DKIM conclusion

The generic blocker that no DKIM DNS evidence exists is replaced with the narrower blocker:

```text
dkim_signing_alignment_unverified
```

The accepted public key proves DNS record presence only. It does not prove:

- that Namecheap currently signs outgoing WW.CX messages;
- that the provider uses selector `default` on a sent message;
- that the DKIM signing domain aligns with the visible From domain;
- that a receiving system reports DKIM pass;
- that SPF aligns with the envelope sender;
- that DMARC passes;
- that `john@ww.cx` exists as a provider-authorized sender.

Those facts require complete received headers from one separately authorized controlled pilot message after every other provider and gateway gate is ready.

## Refined provider conclusion

The prior absence of any substantive WW.CX provider inventory is closed. The remaining provider blocker is narrower:

- canonical private and shared delivery mailboxes are not observed;
- the canonical `john@ww.cx` sender is not observed;
- mailbox access owners are unknown;
- forwarding, retained-copy behavior, and filters are unknown;
- hosting-side routing is unknown;
- no provider sender-authentication test has occurred.

The observed mailboxes are not silently substituted for canonical identities.

## First provider candidate

The current implementation supports authenticated SMTP submission, so the evidence report identifies the first possible provider candidate as:

```text
gateway_profile=smtp_submission
provider_family=namecheap_private_email
provider_selected=false
provider_terms_reviewed=false
credentials_installed=false
canonical_sender_available=false
ready=false
```

This is a planning candidate, not a provider selection or commercial decision.

## Current state

The committed system remains:

```text
readiness_state=safe_disabled
ready_for_provider_activation=false
runtime_credentials_inspected=false
network_or_dns_queries_performed=false
configuration_modified=false
message_prepared=false
message_sent=false
```

The evidence-aware report cannot enable a sender or provider. It fails closed if an accepted record claims provider signing, header alignment, sender readiness, inferred mailbox access, or any activation authority.

## Remaining blockers before a pilot

1. Complete read-only WW.CX forwarding, filter, access-owner, and routing evidence.
2. Decide and provision the canonical internal mailboxes and one sender identity through a separately authorized provider change with rollback.
3. Review the selected provider's terms, limits, SMTP authentication method, message-size limits, and acceptable-use requirements.
4. Define the exact envelope sender and aligned return-path.
5. Confirm SPF coverage for the selected path and establish DMARC reporting before any policy change.
6. Implement bounce, complaint, suppression, and quarantine handling.
7. Install provider credentials through an approved secret path.
8. Prepare a runtime-only activation overlay enabling exactly one provider and one sender.
9. Authorize one WW.CX-controlled recipient and one exact pilot message.
10. Preserve full received headers and reconcile provider acceptance, DKIM, SPF, DMARC, message ID, gateway audit, and rollback evidence.

## Preserved boundaries

This package performs no provider login, credential inspection, public DNS query, DNS change, mailbox change, sender activation, provider activation, gateway activation, message preparation, or message delivery.
