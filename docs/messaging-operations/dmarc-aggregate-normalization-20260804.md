# DMARC aggregate-report normalization

Date: 2026-08-04

## Objective

Convert a restricted, authenticated DMARC aggregate XML attachment into minimized WW.CX authentication and alignment evidence without retaining raw source IPs, report email addresses, report IDs, selectors, XML, credentials, or message content.

Components:

- evidence schema: `schemas/messaging/dmarc-aggregate-evidence.schema.json`;
- offline normalizer: `tools/messaging/normalize_dmarc_aggregate_report.py`;
- validator: `tests/validate_dmarc_aggregate_normalizer.py`.

The package does not access a mailbox, query DNS, contact a provider, expose a listener, or send mail.

## Evidence prerequisite

A DMARC aggregate XML attachment must remain in a restricted evidence directory outside every Git working tree. Its manifest records:

- authenticated mailbox-attachment source;
- `source_verified=true` from a separate capture procedure;
- SHA-256 of the mailbox identity;
- SHA-256 of the raw XML;
- SHA-256 of the attachment filename;
- expected policy domain `ww.cx`;
- explicit restricted-raw-report and no-credential/no-message-content markers.

The normalizer verifies the raw XML SHA-256. It cannot create or infer mailbox authentication.

## XML safety

The normalizer:

- limits raw XML to 20 MiB;
- rejects DTD and entity declarations before parsing;
- uses the standard-library non-network parser;
- accepts only a `feedback` aggregate report;
- limits reports to 10,000 records and 10,000,000 represented messages;
- rejects duplicate or missing required elements;
- rejects malformed IP addresses, domains, counts, auth results, and dispositions;
- refuses input or output paths inside the repository.

## Policy boundary

The report must describe the exact initial WW.CX monitoring policy:

```text
policy domain = ww.cx
p = none
sp = none
adkim = relaxed
aspf = relaxed
pct = 100
```

A report describing quarantine, reject, strict alignment, another domain, or partial application fails closed. This prevents a silently changed DNS policy from being treated as the approved monitoring baseline.

## Source-IP minimization

The raw IPv4 or IPv6 address is parsed only long enough to validate and canonicalize it. The output stores:

- IP family (`4` or `6`);
- a report-scoped SHA-256 pseudonym derived from the raw report hash and canonical IP.

The same IP has a deterministic pseudonym within one report, supporting record aggregation and review. A different report hash produces a different pseudonym, preventing stable cross-report tracking without a separately approved keyed-correlation system.

The raw IP is not emitted.

## Authentication and alignment

For every record, the normalizer retains bounded evidence:

- represented message count;
- header-from and envelope-from domains;
- receiver disposition and policy-evaluated DKIM/SPF result;
- DKIM domain, hashed selector, result, and computed alignment;
- SPF domain, scope, result, and computed alignment;
- computed DMARC aligned result;
- whether the receiver summary disagrees with the independent computation.

Relaxed alignment treats the policy domain and its subdomains as aligned. DMARC passes when at least one passing DKIM or mail-from SPF result aligns.

The normalizer does not decide whether a source is authorized. Output remains:

```text
source_authorization_assessed=false
unknown_source_count=null
```

A later approved source inventory may classify report-scoped sources, but the aggregate parser does not infer authorization from pass/fail alone.

## Report metadata minimization

The receiving organization name is retained. The report email and report ID are reduced to SHA-256. Raw attachment names are represented only by the manifest hash.

The raw XML remains in restricted evidence and is not copied into normalized output.

## Offline command

```sh
python3 tools/messaging/normalize_dmarc_aggregate_report.py \
  --xml /restricted/dmarc/<timestamp>/report.xml \
  --manifest /restricted/dmarc/<timestamp>/manifest.json \
  --output /restricted/dmarc/<timestamp>/normalized.json \
  --pretty
```

## Retention and review

Before production use, define:

1. restricted raw-attachment retention;
2. normalized-report retention;
3. access owners and recovery owners;
4. mailbox attachment capture and manifest generation;
5. duplicate attachment detection using SHA-256;
6. monitoring for parse failures and receiver-computation mismatches;
7. approved outbound-source inventory for authorization assessment;
8. incident handling for newly unaligned or enforcement-disposition traffic.

The first monitoring period should not automatically alter SPF, DKIM, DMARC, provider, sender, or suppression state.

## Remaining live dependencies

- access to the chosen aggregate-report mailbox is not verified;
- receipt of a controlled test message is not verified;
- no DMARC record has been authorized or published;
- no aggregate XML has been received;
- no provider sending credential or canonical sender is active;
- the controlled pilot has not been authorized or sent.

## Preserved boundaries

This package performs no mailbox access, network request, DNS query or mutation, credential inspection, provider/sender activation, gateway cutover, message preparation, or message traffic.
