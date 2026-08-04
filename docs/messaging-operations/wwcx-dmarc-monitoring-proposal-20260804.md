# WW.CX DMARC monitoring proposal

Date: 2026-08-04

## Objective

Produce an exact, conservative DMARC monitoring record for review without querying or changing DNS, accessing a mailbox, installing a credential, activating a sender/provider, or sending mail.

Tool:

```text
tools/messaging/wwcx_dmarc_monitoring_proposal.py
```

The tool reconciles only committed accepted evidence:

- Namecheap Private Email provider inventory;
- August 4 WW.CX DNS acceptance;
- August 4 WW.CX DKIM DNS acceptance.

## Proposed record

For the default observed report mailbox, the exact proposal is:

```text
Name:  _dmarc.ww.cx
Type:  TXT
Value: v=DMARC1; p=none; sp=none; adkim=r; aspf=r; pct=100; rua=mailto:domaincontact@ww.cx; ri=86400
```

Properties:

- organizational policy: `none`;
- subdomain policy: `none`;
- DKIM alignment: relaxed;
- SPF alignment: relaxed;
- percentage: 100;
- aggregate interval: 86,400 seconds;
- aggregate destination: `domaincontact@ww.cx`;
- forensic reporting: not requested.

The proposal deliberately excludes `ruf` because forensic failure reports can contain message-derived data and require a separate privacy, retention, access, and operational decision.

## Evidence supporting the proposal

Accepted evidence shows:

- WW.CX currently has no published DMARC record;
- WW.CX publishes one accepted Namecheap Private Email SPF record;
- `default._domainkey.ww.cx` has a valid-shape public DKIM record;
- `domaincontact@ww.cx` is an active provider-observed WW.CX mailbox;
- `blank@ww.cx` is the only other active provider-observed mailbox.

The provider inventory does not prove who can access either mailbox. The DKIM DNS record does not prove that outgoing messages are signed or aligned.

## Current readiness

The proposal output must remain:

```text
record_syntax_ready=true
report_destination_object_observed=true
report_destination_access_ready=false
report_processing_ready=false
dns_change_ready=false
pilot_authentication_ready=false
```

It also preserves:

```text
dns_change_authorized=false
mailbox_access_authorized=false
report_processing_authorized=false
provider_or_sender_activation_authorized=false
message_authorized=false
```

The tool cannot change these flags through command-line options.

## Command

```sh
python3 tools/messaging/wwcx_dmarc_monitoring_proposal.py \
  --report-address domaincontact@ww.cx \
  --pretty \
  --output /tmp/wwcx-dmarc-monitoring-proposal.json
```

A different aggregate-report address is accepted only when it is an active mailbox in the committed WW.CX provider inventory. An external or unobserved address fails closed.

## Required evidence before DNS authorization

1. Authenticate to `domaincontact@ww.cx` through an approved credential path without exposing credentials.
2. Prove the mailbox can receive and retain a controlled non-sensitive test message.
3. Assign an access owner and recovery owner.
4. Define where aggregate XML reports will be stored, parsed, retained, and reviewed.
5. Define alerting for SPF/DKIM alignment changes and unknown sources.
6. Capture the exact authoritative DNS zone and rollback record through a read-only provider session.
7. Obtain explicit authorization for the exact `_dmarc.ww.cx` TXT addition.
8. Apply only `p=none`; do not combine the first publication with quarantine or reject enforcement.
9. Verify the published record through independent resolvers and preserve evidence.
10. Run the separately authorized one-message pilot and verify receiver-reported DMARC pass and alignment.

## Rollback expectation

A later DNS activation package must preserve the pre-change record state, apply one exact TXT record, verify independent resolver convergence, and automatically restore the prior state if the published value differs from the approved proposal or external validation fails.

This proposal does not implement that DNS mutation package.

## Preserved boundaries

The proposal performs no DNS query or mutation, mailbox access, report processing, credential inspection, provider/sender activation, gateway activation, message preparation, or message traffic. It is not permission to publish the record.
