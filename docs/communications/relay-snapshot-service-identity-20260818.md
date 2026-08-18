# Relay snapshot service identity correction — 2026-08-18

## Live failure evidence

The first durable Relay snapshot activation attempts on `edge1.ww.cx` failed before snapshot attachment. Automatic rollback removed the generator, timer, environment file, and state directory, then restored the read-only Communications workspace healthy with zero attached events.

The retained service journal showed `sqlite3.OperationalError: unable to open database file` while opening `/var/lib/wwcx-comms/comms.sqlite3` read-only.

Live filesystem evidence established:

- `/var/lib/wwcx-comms` is owned `wwcx-comms:wwcx-comms`, mode `0750`.
- `/var/lib/wwcx-comms/comms.sqlite3` is owned `wwcx-comms:wwcx-comms`, mode `0600`.
- `wwadmin` is not a member of `wwcx-comms` outside the service context.
- Because the database group permission bits are zero, `SupplementaryGroups=wwcx-comms` cannot make a `User=wwadmin` process able to read the database file.

## Least-privilege identity proof

A no-production-change operator test ran the generator as `wwcx-comms:wwadmin` against the authoritative database.

Accepted results:

- article count: 168
- ingest count: 168
- joined count: 168
- canonical snapshot events: 168
- internal events: 147
- inbound events: 21
- raw body fields: 0
- generated snapshot ownership: `wwcx-comms:wwadmin`
- generated snapshot mode: `0640`
- the existing `wwadmin` workspace identity successfully read and validated all 168 events
- the production workspace remained unattached with zero events
- no database permissions changed
- no production service restarted
- no communications traffic was generated

## Correct service identity

The Relay snapshot generator should therefore run as:

```ini
User=wwcx-comms
Group=wwadmin
```

This preserves the authoritative Relay database at mode `0600`, gives the generator owner access to that database, and makes atomically generated `0640` snapshots readable by the existing Communications workspace through group `wwadmin`.

`SupplementaryGroups=wwcx-comms` is intentionally removed because the process already runs as the database owner.

## Unchanged boundaries

This correction does not authorize or implement message send, mail send, call origination, routing changes, quarantine release, Relay mutation, database permission relaxation, public listeners, or production traffic generation.
