# Telephony Analytics Report Audit Events

## Purpose

The report-audit foundation records that an already-generated aggregate telephony analytics report was produced. It provides a privacy-minimized, append-only, hash-chained JSONL record without retaining report content, source rows, customer identifiers, telephone numbers, SIP URIs, credentials, network addresses, file paths, or free-form metadata.

This foundation does not generate a report and does not read a live telephony source.

## Append-only contract

Runtime records use one JSON object per line. `server/telephony_report_audit.py` opens the target with:

- `O_APPEND` so each write is placed at the end;
- `O_NOFOLLOW` so the final path cannot be a symlink;
- an exclusive `flock` while verifying and appending;
- owner-only file permissions;
- `fsync` after each append.

The parent directory must already exist, must not itself be a symlink, and should be a protected runtime directory. The log path must be absolute and use the `.jsonl` suffix.

The module refuses a log that:

- is not a regular file;
- is owned by another effective user;
- grants group or other permissions;
- contains an empty, malformed, non-newline-terminated, or invalid event;
- has a broken previous-hash reference or event-content hash.

## Privacy-minimized event fields

Input contract:

```text
schemas/telephony/analytics-report-audit-input.schema.json
```

Stored event contract:

```text
schemas/telephony/analytics-report-audit-event.schema.json
```

Each event contains only:

- schema version and fixed event type;
- opaque event and report identifiers;
- RFC 3339 UTC occurrence time;
- bounded report kind;
- opaque generator identifier;
- full repository revision;
- SHA-256 of the sanitized input manifest;
- SHA-256 of the generated report artifact;
- aggregate record count;
- fixed privacy profile;
- previous event SHA-256;
- current event SHA-256.

Allowed report kinds are:

- `health_summary`;
- `call_summary`;
- `interconnect_summary`;
- `combined_summary`.

The fixed privacy profile is:

```text
aggregate_no_customer_identifiers
```

Unknown fields are rejected. The event contract does not include report paths, report titles, names, telephone numbers, account numbers, SIP/TEL URIs, email addresses, IP addresses, call IDs, route identifiers, credentials, message bodies, SDP, media, recordings, or arbitrary metadata.

## Hash-chain verification

The first event uses 64 zeroes as `previous_event_sha256`.

For each event, `event_sha256` is the SHA-256 of canonical JSON containing every event field except `event_sha256`. Canonical JSON uses sorted keys, ASCII output, and no insignificant whitespace.

Before appending, the module verifies every existing line from the first event forward. A changed field, removed line, reordered chain, broken previous hash, malformed final line, or invalid event prevents the append.

The verification result contains only:

- event count;
- final event SHA-256;
- `chain_valid=true`.

## CLI

The bounded CLI is:

```text
tools/telephony/append_analytics_report_audit.py
```

Append one pre-minimized input event:

```bash
python3 tools/telephony/append_analytics_report_audit.py \
  --audit-log /absolute/protected/path/report-audit.jsonl \
  --event-file /absolute/path/to/minimized-event.json
```

Verify an existing chain:

```bash
python3 tools/telephony/append_analytics_report_audit.py \
  --audit-log /absolute/protected/path/report-audit.jsonl \
  --verify-only
```

The CLI prints only the appended event ID, current and previous hashes, or the minimized verification summary. It does not print report content.

## No report job or service activation

This repository increment does not:

- schedule or generate reports;
- connect a CDR, SIP, PBX, messaging, carrier, or database source;
- install or start a service or timer;
- modify the running console or analytics API;
- create a runtime audit directory;
- append a live audit event;
- originate a call or message;
- transmit DTMF;
- alter a route, carrier, credential, listener, firewall, DNS, or certificate.

Live use requires a separately reviewed report generator, protected runtime directory, retention policy, ownership model, source-minimization proof, and operator deployment evidence.

## Synthetic fixtures

Input example:

```text
examples/telephony/analytics-report-audit-input.example.json
```

Stored chained example:

```text
examples/telephony/analytics-report-audit-event.example.json
```

Both fixtures are synthetic and contain placeholder hashes only.

## Validation

From the repository root:

```bash
python3 tests/validate_telephony_report_audit.py
```

The test covers:

- canonical first and second event appends;
- event-chain verification;
- preservation of existing bytes during append;
- owner-only mode;
- changed-content detection;
- non-newline-terminated record rejection;
- group-readable log rejection;
- symlink rejection;
- relative-path rejection;
- unknown-field and customer-identifier rejection;
- invalid timestamp, report kind, privacy profile, and count rejection;
- absence of network, database, subprocess, PBX, or service-control access paths.

## Acceptance boundary

A valid report-audit chain proves only that the stored minimized events are internally hash-linked and unchanged under this validator. It does not prove report correctness, source completeness, lawful source access, carrier interoperability, route readiness, emergency-calling readiness, regulatory compliance, or production authorization.
