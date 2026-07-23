# Telephony Analytics History Design

## Purpose

Provide local append-only storage for sanitized telephony analytics snapshots.

## Safety Boundary

This component:

- stores analytics history only;
- performs no PBX operations;
- performs no carrier operations;
- performs no routing changes;
- contains no credential handling.

## Storage

SQLite local database:

`data/telephony/history/analytics-history.sqlite3`

## Initial Operations

- initialize storage;
- record snapshots;
- retrieve recent snapshots;
- retrieve latest snapshot.

Future API exposure must remain read-only.
