# Mail Room threat decision and quarantine runtime — 2026-08-18

## Scope

This repository increment turns the existing staged Mail Room threat policy into provider-neutral, executable decision contracts without installing or activating antivirus, YARA, reputation, AI, sandbox, provider, or production routing services.

`server/mail_threat_decision.py` consumes normalized security facts. `server/mail_quarantine.py` creates sanitized quarantine metadata and evaluates whether a future authorized operator workflow has satisfied release prerequisites. Neither module accepts raw MIME or attachment bytes.

## Threat decision rules

Required malware scanning fails closed. A missing required scan, or any normalized state other than `clean`, produces a quarantine hard block. Supported scan states are `clean`, `infected`, `suspicious`, `unscannable`, `scan_error`, and `not_scanned`.

DMARC failure, high/critical phishing risk, and high/critical BEC risk are hard security blocks. AI-derived risk may escalate an otherwise clean message to quarantine but cannot downgrade a hard block. The decision result explicitly reports that AI may not reduce hard security risk and may not release quarantine.

The runtime consumes normalized authentication and scanner facts only. MIME parsing, attachment execution, URL browsing, external reputation lookups, and AI calls are intentionally outside this decision module.

## Quarantine record

Quarantine metadata is bounded to identifiers, hashes, reason codes, normalized security signals, scanner engine/ruleset metadata, timestamps, route decision, and provenance. General quarantine metadata explicitly records that message bodies and attachment bytes are not stored there and active content was not executed.

Unique accepted correspondence is not deleted by this contract. There is no delete function and no automatic release function.

## Release boundary

Release eligibility requires all of the following authoritative gates:

- explicit operator approval;
- a clean security rescan;
- validated release destination;
- policy authorization.

An AI-requested release is itself a blocking reason. AI never satisfies operator approval, never creates policy authority, and never performs release. The evaluator only reports whether prerequisites have been met; an actual release operation remains a separately privileged workflow.

## Production boundary

No production scanner, quarantine store, provider webhook, mailbox, DNS, credentials, external security service, or production routing was activated. These contracts are repository foundations for later trusted adapters and operator workflows.
