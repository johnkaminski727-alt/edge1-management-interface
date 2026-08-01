# Mail Provider Reconciliation Status — 2026-08-01

## Decision

Continue all read-only and offline reconciliation work while the Namecheap Private Email inventory request for `ww.cx` is pending. Keep this follow-up branch unmerged until the provider reply has been reviewed and normalized.

No mailbox, alias, forwarder, filter, routing mode, DNS record, authentication setting, sender authorization, or production mail flow is authorized by this record.

## Shared-hosting evidence accepted for processing

A cPanel UAPI capture completed successfully at `2026-08-01T07:01:57Z` for:

- `creekco.ca`;
- `scgardens.ca`;
- `omegafx.com`.

The capture:

- authenticated with a temporary cPanel API token only after a read-only probe succeeded;
- collected 13 provider JSON responses plus `metadata.json`;
- generated `SHA256SUMS` covering all 14 JSON files;
- verified every listed SHA-256 value successfully;
- retained raw evidence only in a restricted local evidence directory;
- did not place raw provider data in Git;
- had its temporary API token revoked after capture.

The earlier HTTP Basic attempt returned 401 and produced only local metadata. That directory is failed evidence and must not be used for reconciliation.

## Offline normalization

Use the repository normalizer against the successful restricted evidence directory:

```powershell
$Repo = 'C:\path\to\edge1-management-interface'
$Evidence = 'C:\path\to\Private Mail Evidence\business159-20260801T070157Z'
$Inventory = Join-Path $Evidence 'namecheap-shared-hosting.normalized.json'

python "$Repo\tools\messaging\normalize_cpanel_mail_inventory.py" `
  --evidence-dir $Evidence `
  --output $Inventory
```

The normalizer:

- verifies the SHA-256 manifest before parsing;
- accepts only successful UAPI result envelopes;
- refuses evidence or output paths inside a Git working tree;
- maps observed mailboxes and forwarders into `wwcx.provider-mail-objects.v1`;
- classifies canonical private and shared addresses from the inbound-hub registry;
- conservatively leaves outbound sender authorization unproven;
- records cPanel domain-routing mode as `unknown` pending separate verification;
- fails closed when domain-level forwarders, account filters, or autoresponders are present, because those behaviors require manual restricted review.

The resulting normalized inventory remains restricted operational metadata and must not be committed.

## Partial reconciliation

A partial report can be generated before the `ww.cx` provider reply arrives:

```powershell
$Report = Join-Path $Evidence 'shared-hosting-partial-reconciliation.json'

python "$Repo\tools\messaging\reconcile_mail_provider_objects.py" `
  --inventory $Inventory `
  --output $Report
```

Do not use `--strict` for the partial report. Missing `ww.cx` Private Email objects and the unresolved `spiritcreekgardens.com` provider state are expected blockers. The partial report is useful for identifying shared-hosting mailboxes, exact forwarders, inactive objects, destination mismatches, unexpected addresses, catch-all behavior, and unknown routing modes.

## Pending Namecheap Private Email evidence

A read-only inventory request was sent to Namecheap Private Email Support for the existing `ww.cx` subscription. The request asks for:

- subscription status and mailbox capacity;
- configured mailboxes and active state;
- aliases and groups;
- catch-all behavior;
- quotas and forwarding;
- DKIM status and selector;
- alias sender capability;
- provider-side rules or filters.

The request expressly prohibits provider changes and excludes passwords, tokens, reset links, and other authentication secrets.

When the reply arrives:

1. preserve the message as restricted provider evidence;
2. verify whether the response is complete and whether a fresh Support PIN is required;
3. normalize the `ww.cx` objects into a separate `namecheap_private_email` inventory;
4. run the combined reconciliation with both provider inventories;
5. update the issue and this branch with sanitized counts and conclusions only;
6. merge only after CI passes and the provider response closes or explicitly documents every remaining unknown.

## Remaining blockers

- current provider object types and destinations for all `ww.cx` identities;
- existence and access classification of `john-inbox@ww.cx` and `maildesk@ww.cx`;
- `ww.cx` catch-all, filtering, forwarding, and DKIM state;
- separate cPanel domain-routing verification for the three shared-hosting domains;
- authoritative provider state for `spiritcreekgardens.com`;
- any provider mutation, pilot forwarding, sender activation, or production cutover authorization.
