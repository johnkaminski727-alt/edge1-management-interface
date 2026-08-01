# Telephony Aggregate Report Generator

## Purpose

The generator converts one already-aggregated, privacy-minimized telephony snapshot into a deterministic JSON and Markdown report bundle. It is an offline repository capability only.

## Already-aggregated input contract

The input contains only:

- an opaque report identifier;
- a UTC generation timestamp;
- a full repository revision;
- the fixed `combined_summary` report kind;
- the accepted platform-health summary;
- the accepted aggregate call summary;
- the accepted aggregate interconnect summary.

The generator recomputes the informational anomaly contract from those three summaries. It does not accept raw CDRs, SIP messages, telephone numbers, SIP or TEL URIs, email or IP addresses, message bodies, headers, SDP, media, recordings, credentials, customer metadata, arbitrary notes, or unknown fields.

## Owner-only bundle

A successful write creates one new mode-`0700` directory containing mode-`0600` regular files:

```text
report.json
report.md
report-audit-input.json
SHA256SUMS
```

The output parent must already exist and must not be a symlink. The target directory must not exist. Every artifact is created with `O_EXCL` and `O_NOFOLLOW`, flushed with `fsync`, and verified after creation.

## Audit-event candidate

`report-audit-input.json` is a candidate for the existing hash-chained report-audit tool. It records only opaque identifiers, timestamps, hashes, aggregate record count, repository revision, report kind, generator identity, and the fixed privacy profile.

Generation does not append a live audit log. An operator must separately review the report bundle and invoke the accepted append-only audit tool if a durable event is required.

## No overwrite

The generator never replaces an existing report directory or file. A collision, symlink, non-regular input, malformed JSON, invalid aggregate contract, unsafe identifier, non-finite value, or permission problem fails closed. Files created during an incomplete new-bundle attempt are removed only from that newly created directory.

## No scheduler or runtime activation

This increment does not install a service, timer, cron entry, runtime directory, retention policy, collector, API route, or console control. It does not contact the live analytics service or any PBX, SIP edge, carrier, database, log, packet source, or network endpoint.

It cannot dispatch notifications, enforce traffic, change routes, control services, originate calls, send messages, or transmit DTMF.

## Offline use

From a clean repository checkout, prepare a JSON file conforming to:

```text
schemas/telephony/analytics-report-input.schema.json
```

Validate without creating output:

```bash
python3 tools/telephony/generate_telephony_analytics_report.py \
  --input /absolute/path/input.json \
  --output-dir /absolute/path/new-report-directory \
  --validate-only
```

Generate a new owner-only bundle:

```bash
python3 tools/telephony/generate_telephony_analytics_report.py \
  --input /absolute/path/input.json \
  --output-dir /absolute/path/new-report-directory
```

No command in this runbook authorizes collection from a live source or deployment of a scheduled report job.
