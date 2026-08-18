# Mail Room canonical domain and configuration consistency — 2026-08-18

## Canonical source

`config/messaging/mail-identities.json` is the canonical configured set of WW.CX-managed mail domains. Inbound routing, outbound allowed domains, provider inventory, and read-only DNS inventory tooling may carry domain-specific operational data, but their domain sets must remain consistent with that registry.

## Drift validator

`server/mail_config_consistency.py` fails validation when:

- inbound managed domains differ from the identity registry;
- outbound allowed sender domains differ from the identity registry;
- provider inventory domains differ from the identity registry;
- inbound routes or sender mappings refer to a domain outside the canonical set;
- canonical internal delivery/system addresses disagree between identity and provider inventory records.

The validator is read-only and performs no provider, DNS, mailbox, or routing changes.

## DNS inventory refactor

`tools/messaging/mail_domain_inventory.py` no longer hard-codes the five managed domains in source code. By default it loads the canonical identity registry and inventories exactly those configured domains. A different identity-registry path may be supplied explicitly for testing or staged administration.

This reduces the source-code work required for a future domain lifecycle operation. Adding or retiring a domain still requires coordinated configuration changes and historical provider records must not be erased, but the DNS inventory tool no longer requires a source edit merely to recognize the configured domain set.

## Production boundary

No domain was added, suspended, retired, activated, or removed. No MX, SPF, DKIM, DMARC, NS, mailbox, forwarding, provider, or production routing state was changed.
