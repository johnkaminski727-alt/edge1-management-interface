# Namecheap Private Email support evidence intake

## Purpose

Normalize a sanitized, read-only Namecheap Private Email support response into the provider-object reconciliation contract without storing raw email, credentials, verification material, or secret-bearing fields in Git.

Ticket `NC-JDV-2953` has already produced accepted provider-visible facts for `ww.cx`. Those facts are preserved in:

```text
records/messaging/provider-inventories/namecheap-private-email-wwcx-20260802.json
```

The accepted record confirms two active mailboxes, no aliases, Catch-All to `blank@ww.cx`, mailbox quotas, provider-reported send/receive configuration, and default-selector DKIM. It deliberately leaves mailbox access, forwarding, filters, hosting-side routing, authenticated sender behavior, and canonical mailbox mapping unresolved.

## Evidence boundary

Raw provider correspondence and any verification response remain outside Git in a restricted evidence directory. Never store or pass through the normalizer:

- passwords or support PINs;
- API or OAuth tokens;
- authorization headers;
- cookies or session identifiers;
- reset or activation links;
- private keys;
- mailbox message bodies;
- recovery codes;
- browser exports containing authenticated URLs.

The normalizer rejects secret-bearing field names recursively and verifies `SHA256SUMS` before parsing. Unproven boolean capabilities are normalized to `false`; unknown facts are never promoted from provider prose.

## Sanitized input contract

Prepare one structured JSON record using:

```text
examples/messaging/namecheap-private-email-support-evidence.example.json
```

The structured file may contain provider-visible mailbox objects, subscription metadata, Catch-All behavior, DKIM status, and explicit completeness flags. It must not contain raw correspondence or verification material.

Place the JSON file and any sanitized supporting text in a restricted directory outside every Git working tree, then create the manifest:

```sh
cd /restricted/namecheap-private-email/<timestamp>
find . -maxdepth 1 -type f ! -name SHA256SUMS -print | sort | xargs sha256sum > SHA256SUMS
chmod 0700 .
chmod 0600 ./*
```

## Offline normalization

```sh
python3 tools/messaging/normalize_namecheap_private_email_support.py \
  --evidence-dir /restricted/namecheap-private-email/<timestamp> \
  --output /restricted/namecheap-private-email.json \
  --summary-output /restricted/namecheap-private-email-completeness.json
```

Use `--strict-completeness` only when every required section has genuinely been reviewed. A strict failure is evidence of an unresolved provider gap, not permission to fill missing values optimistically.

The normalizer performs no network requests, no provider login, no subprocess execution, and no mailbox or DNS mutation. Access classes are derived from the canonical repository configuration rather than accepted from support prose.

## Current accepted and unresolved state

Accepted provider-visible facts for `ww.cx`:

- active Pro subscription at the evidence date;
- three mailbox slots, two occupied;
- active `blank@ww.cx` and `domaincontact@ww.cx` mailboxes;
- no aliases;
- Catch-All to `blank@ww.cx`;
- 10 GB quota per mailbox;
- provider-reported send/receive configuration;
- provider-reported default DKIM selector.

Still unresolved:

- who can access each mailbox;
- auto-forward enabled state, destination, and retained-copy behavior;
- mailbox filter rules and actions;
- authoritative hosting-side routing mode;
- authenticated sender and From-address restrictions;
- independently verified DKIM selector label, signing, and alignment;
- existence of `john-inbox@ww.cx` and `maildesk@ww.cx`;
- whether the observed mailboxes should be retained, migrated, renamed, or retired.

## Reconciliation

```sh
python3 tools/messaging/reconcile_mail_provider_objects.py \
  --inventory /restricted/namecheap-private-email.json \
  --inventory /restricted/namecheap-shared-hosting.json \
  --inventory /restricted/namecheap-shared-hosting-routing.json \
  --output /restricted/mail-provider-reconciliation.json \
  --strict
```

The current accepted partial record is not ready for pilot. The two observed WW.CX mailboxes remain unexpected relative to the canonical route model, Catch-All is a warning, routing is unknown, and both canonical internal destinations remain unobserved.

## Stop conditions

Stop before requesting or exposing new verification material, logging into mailboxes, changing aliases or forwarding, modifying filters, changing Catch-All or routing, provisioning or deleting mailboxes, modifying DNS, installing provider credentials, activating a sender, enabling delivery, or sending a message unless that exact action is separately authorized.
