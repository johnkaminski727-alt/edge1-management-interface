# Sanitized Telephony Event Adapters

## Purpose

`server/telephony_sanitized_adapters.py` converts already-sanitized CDR-style records and SIP outcome events into the privacy-minimized `CallEvent` model used by `server/telephony_platform.py`.

This increment is an offline library and contract only. It does not read a CDR database, AMI/ARI socket, SIP trace, packet capture, carrier API, log file, credential store, or production service.

## Fail-closed boundary

The adapters accept only explicit scalar fields. Unknown fields are rejected rather than silently retained or dropped because an unknown field may contain a telephone number, account identifier, SIP URI, credential, address, message body, or other sensitive data.

Every record must contain:

- schema version `1.0`;
- an opaque lowercase `source_record_id` that begins with a letter;
- an RFC 3339 UTC `observed_at` timestamp ending in `Z`;
- normalized direction and event outcome fields appropriate to the adapter.

Batch helpers fail the entire batch on the first rejected record. They do not return a partially accepted result.

## Sanitized CDR contract

Canonical schema:

```text
schemas/telephony/sanitized-cdr-record.schema.json
```

Synthetic example:

```text
examples/telephony/sanitized-cdr-record.example.json
```

Accepted canonical fields:

- `schema_version`;
- `source_record_id`;
- `observed_at`;
- `direction`;
- `disposition`;
- optional `sip_code`;
- optional opaque `carrier_id`;
- optional two-letter `destination_country` or `unknown`;
- `duration_seconds` from `0` through `604800`.

The Python adapter also recognizes bounded source aliases such as `call_direction`, `status`, `response_code`, `provider_id`, `country_code`, and `billsec`. Alias support does not permit additional free-form fields.

## Sanitized SIP-event contract

Canonical schema:

```text
schemas/telephony/sanitized-sip-event.schema.json
```

Synthetic example:

```text
examples/telephony/sanitized-sip-event.example.json
```

Accepted canonical fields:

- `schema_version`;
- `source_record_id`;
- `observed_at`;
- lowercase operational `event_type`;
- `direction`;
- optional bounded `disposition`;
- optional `sip_code`;
- optional opaque `carrier_id`;
- optional two-letter `destination_country` or `unknown`;
- optional bounded `duration_seconds`.

When a sanitized SIP event omits `disposition`, the adapter derives only a conservative outcome class:

- `100-199` becomes `progress`;
- `200-299` becomes `completed`;
- `300-699` becomes `failed`;
- no response code becomes `unknown`.

This derivation is not a root-cause claim.

## Explicitly rejected data

The adapters reject:

- calling-party and called-party numbers;
- caller ID, ANI, DNIS, source, destination, account-code, and user-field columns;
- SIP or TEL URIs;
- email and IP addresses;
- Call-ID, channel, unique ID, linked ID, contact, From, To, and header fields;
- authorization values, credentials, passwords, secrets, and tokens;
- SDP, media, recording, message, and body fields;
- names and free-form metadata objects;
- opaque IDs containing long numeric sequences;
- nested mappings, lists, tuples, or sets;
- unsupported fields, schema versions, directions, dispositions, countries, SIP codes, durations, or timestamps.

The shared `CallEvent.metadata` output contains only adapter identity, schema version, the opaque source record ID, the normalized observation timestamp, and—for SIP events—the operational event type.

## No live collector activation

This change does not install or activate a collector. It does not modify the existing analytics service, data files, systemd unit, listener, API, database privileges, credentials, carrier configuration, PBX configuration, routes, or runtime source.

A future live collector must have a separately reviewed design that proves minimization occurs before data reaches these adapters. Database, AMI/ARI, SIP-edge, log, or carrier access remains separately gated.

## Validation

From the repository root:

```bash
python3 tests/validate_telephony_sanitized_adapters.py
```

The validation exercises canonical and alias inputs, conservative SIP disposition derivation, full-batch rejection, schema markers, and negative cases for raw caller fields, unknown fields, nested metadata, telephone-like identifiers, SIP URIs, IP addresses, malformed timestamps, invalid country codes, invalid durations, invalid SIP codes, and unsupported schema versions.

## Safety conclusion

These adapters provide a bounded normalization boundary for synthetic or independently sanitized inputs. Passing the adapter does not prove source-system compliance, carrier interoperability, production routing, emergency-calling readiness, regulatory status, or authorization to connect a live data source.
