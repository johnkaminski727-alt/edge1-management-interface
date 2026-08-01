# Provider Mail Object Capture and Reconciliation

## Status

This procedure gathers and reconciles provider-side mailbox metadata without changing mail service. It is the required evidence step before provisioning `john-inbox@ww.cx`, provisioning `maildesk@ww.cx`, creating or changing forwarders, or enabling any inbound or outbound gateway path.

Public DNS shows which provider receives mail, but it does not reveal whether an address is implemented as a mailbox, alias, forwarder, distribution list, catch-all, filter, or inactive object. The canonical hub currently defines 37 public routes, two internal delivery mailboxes, and one outbound-only system sender. Provider evidence must be reconciled against that model.

## Safety boundary

The capture and reconciliation tools:

- do not accept provider passwords or API tokens;
- do not store credentials;
- do not create, edit, delete, suspend, or enable mail objects;
- do not change MX, SPF, DKIM, DMARC, email routing, filters, or forwarding;
- refuse to place raw cPanel evidence inside a Git working tree;
- mark raw evidence as restricted operational metadata;
- write SHA-256 checksums for the captured evidence;
- operate offline after evidence has been collected.

Raw provider exports can disclose addresses, forwarding destinations, quotas, account names, filters, and routing behavior. Store them in a restricted evidence directory, not in the repository or a generally shared Drive folder.

## cPanel shared-hosting capture

The Namecheap shared-hosting domains currently include `creekco.ca`, `scgardens.ca`, and `omegafx.com`. Run the capture script from a shell where the cPanel `uapi` command is available:

```sh
umask 077

./tools/messaging/capture_cpanel_mail_inventory.sh \
  --output "$HOME/private-mail-evidence/$(date -u +%Y%m%dT%H%M%SZ)" \
  --user YOUR_CPANEL_USER \
  --domain creekco.ca \
  --domain scgardens.ca \
  --domain omegafx.com
```

The script invokes only these read operations:

```text
Email list_mail_domains
Email list_pops
Email list_domain_forwarders
Email list_forwarders
Email list_default_address
Email list_auto_responders
Email list_filters
```

It validates that every UAPI response reports success and writes `SHA256SUMS` plus restricted `metadata.json`.

The official cPanel UAPI documentation identifies `Email::list_pops` as the email-account listing function, `Email::list_forwarders` and `Email::list_domain_forwarders` as forwarder listing functions, and `Email::list_default_address` as the default or catch-all address inspection function. The capture script intentionally excludes all corresponding mutation functions.

## Namecheap Private Email capture

`ww.cx` currently publishes Namecheap Private Email MX records rather than cPanel shared-hosting MX records. The cPanel capture script is therefore not authoritative for WW.CX.

Use the Namecheap Private Email administration interface to record, without modifying:

1. active mailboxes;
2. aliases and groups;
3. forwarding settings and whether a server copy is retained;
4. mailbox quotas;
5. sender aliases and outgoing-mail authorization;
6. recovery and administrator access;
7. filters or rules that forward, discard, or redirect mail;
8. DKIM and domain-verification status.

Screenshots or exports should be stored with the same restricted evidence controls. Do not put passwords, password-reset links, session URLs, or authentication tokens in the normalized inventory.

## Normalized inventory contract

Provider evidence is normalized into:

```text
wwcx.provider-mail-objects.v1
```

The JSON Schema is located at:

```text
schemas/messaging/mail-provider-objects.schema.json
```

An illustrative, deliberately incomplete example is located at:

```text
examples/messaging/mail-provider-objects.example.json
```

Each mail object records:

- normalized address and domain;
- provider object type;
- forwarding or alias destinations;
- whether it receives mail;
- whether the provider can submit mail as that identity;
- active state;
- private/shared/system/unknown access classification;
- optional quota and non-secret notes.

Default-address behavior and cPanel domain-routing mode are recorded separately. A reject-style default address is preferred while the hub uses explicit named routes. Forwarding, blackhole, pipe, automatic, and unknown states require review.

## Reconciliation command

After normalizing one or more provider exports, run:

```sh
python3 tools/messaging/reconcile_mail_provider_objects.py \
  --inventory /restricted/namecheap-private-email.json \
  --inventory /restricted/namecheap-shared-hosting.json \
  --output /restricted/mail-provider-reconciliation.json \
  --strict
```

The tool reads the canonical files by default:

```text
config/messaging/inbound-mail-hub.json
config/messaging/mail-identities.json
```

It supports multiple inventories because WW.CX and the shared-hosting domains are currently on different mail-provider families.

## Reconciliation outcomes

For every canonical public address, the report classifies provider evidence as:

- `exact_forwarder` — an active alias or forwarder reaches the configured internal destination;
- `local_object_present` — an active mailbox, distribution list, or system account exists but migration or forwarding remains pending;
- `forwarder_destination_mismatch` — an active forwarder points somewhere other than the canonical destination;
- `inactive_or_not_receiving` — an object exists but is inactive or not accepting mail;
- `object_present_unknown_type` — provider evidence exists but its behavior is not classified;
- `missing` — no active provider object was observed.

Critical gaps include missing routes, inactive routes, destination mismatches, internal access-class mismatches, and forwarder cycles. Strict mode exits with status `2` while any critical gap remains.

Warnings include:

- unexpected active addresses at a managed domain;
- an address observed at more than one provider;
- catch-all/default-address behavior other than explicit rejection;
- automatic or unknown cPanel email-routing modes.

Sender capability is reported independently. An address existing as an inbound forwarder does not prove that the provider is authorized or configured to send as that identity.

## Required acceptance state before a pilot

A provider reconciliation can support a copied or forwarded pilot only when:

1. all 37 canonical public routes are observed as active provider objects;
2. no active forwarder points to the wrong internal destination;
3. no forwarding cycle exists;
4. `john-inbox@ww.cx` is observed with `private_john` access classification;
5. `maildesk@ww.cx` is observed with `shared_role` access classification;
6. unexpected addresses and catch-all behavior have explicit retention decisions;
7. domain-routing modes are known and consistent with current MX;
8. sender capability is separately verified for any identity proposed for outbound activation;
9. rollback instructions identify the exact provider objects to restore;
10. explicit authorization is obtained before any provider mutation.

A clean report means the inventory matches the intended model. It does not by itself authorize provisioning, forwarding, DNS changes, or production traffic.

## Official references

- cPanel UAPI email accounts: `https://api.docs.cpanel.net/specifications/cpanel.openapi/email-accounts/list_pops`
- cPanel UAPI forwarders: `https://api.docs.cpanel.net/specifications/cpanel.openapi/email-forwarding/list_forwarders`
- cPanel UAPI domain forwarders: `https://api.docs.cpanel.net/specifications/cpanel.openapi/email-forwarding/list_domain_forwarders`
- cPanel UAPI default address: `https://api.docs.cpanel.net/specifications/cpanel.openapi/email-accounts/list_default_address`
- Namecheap cPanel forwarding guide: `https://www.namecheap.com/support/knowledgebase/article.aspx/9205/2214/how-to-set-up-email-forwarding-in-cpanel/`
- Namecheap email-routing guide: `https://www.namecheap.com/support/knowledgebase/article.aspx/9258/31/how-to-change-mx-records-and-email-routing-in-cpanel/`
