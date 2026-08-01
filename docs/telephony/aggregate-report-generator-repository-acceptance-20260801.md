# Telephony Aggregate Report Generator Repository Acceptance — 2026-08-01

## Decision

Accepted at repository level as an offline, privacy-minimized report-generation foundation.

## Already-aggregated input contract

The implementation accepts only the existing aggregate platform-health, call-summary, and interconnect-summary contracts plus fixed report metadata. It recomputes the accepted informational anomaly indicators and rejects unknown fields, inconsistent aggregates, unsafe identifiers, addresses, URIs, non-finite values, raw-event shapes, and unsupported report kinds.

## Owner-only bundle

The accepted output is one newly created mode-`0700` directory containing mode-`0600` `report.json`, `report.md`, `report-audit-input.json`, and `SHA256SUMS` files. Creation uses no-follow, exclusive-create, flush, and post-write permission checks.

## Audit-event candidate

The audit-event candidate conforms to the existing privacy-minimized report-audit input contract. It is not appended automatically. The generated report hash and normalized input-manifest hash are recorded for later reviewed append-only audit use.

## No overwrite

Existing output directories and files are never replaced. Relative output paths, symlink parents, malformed input, permission failures, and output collisions fail closed.

## No scheduler or runtime activation

This acceptance does not create or deploy a report service, timer, cron job, retention policy, runtime directory, audit log, API route, console action, or live source collector. No service is installed, enabled, started, restarted, or reloaded.

## Explicit boundary

The implementation performs no network, PBX, carrier, database, log, packet, credential, call, message, DTMF, routing, notification, enforcement, firewall, DNS, certificate, authentication, or public-listener action.

Live report scheduling, protected runtime paths, retention, automatic audit append, and collection from any live source remain separately reviewed and authorized work.
