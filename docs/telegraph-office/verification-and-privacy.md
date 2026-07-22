# Spirit Creek Telegraph Office verification metadata

The simulator and future operator console may attach optional verification metadata to each dispatch and inbound receipt.

## Time attestation

Record both application and host observations:

- `created_at_utc`: server-generated RFC 3339 UTC timestamp.
- `client_observed_at_utc`: browser-observed timestamp, treated as advisory.
- `ntp_synchronized`: host clock synchronization state.
- `ntp_source`: selected time source name or address when available.
- `clock_offset_ms`: latest measured host offset when available.
- `timezone`: display timezone only; canonical storage remains UTC.

A dispatch requiring verified time must be rejected or clearly marked unverified when the host is not synchronized or the offset exceeds the configured threshold.

## Coordinate attestation

Coordinates are optional and require an explicit operator action for each dispatch or a clearly enabled console session setting.

Record:

- latitude and longitude;
- reported accuracy radius in metres;
- altitude and altitude accuracy when supplied;
- coordinate source (`browser`, `operator`, `preset`, or `device`);
- observation timestamp;
- consent state;
- optional named station preset.

Coordinates are verification claims, not proof of identity. Browser geolocation can be inaccurate or manipulated. The receipt must retain the accuracy radius and source.

## Privacy defaults

- Location collection is off by default.
- Precise coordinates are not included in SMS or MMS bodies unless the operator explicitly selects that option.
- Ledger views show a named station or rounded coordinates by default.
- Exact coordinates are restricted to authorized operator views.
- Coordinates, plaintext, private keys, and passphrases must not be written to ordinary service logs.
- PGP-protected dispatches may include the verification envelope inside the encrypted payload.

## Signed verification envelope

The canonical verification envelope contains message ID, sender identity, recipient identifiers, content digest, media digests, UTC timestamps, clock synchronization state, optional coordinates, coordinate accuracy, and PGP key fingerprints.

The envelope may be digitally signed separately from the message body. This permits integrity verification while allowing plaintext-retention policy to remain `none`.

## Simulator acceptance tests

1. Synchronized UTC dispatch records server and client timestamps.
2. Unsynchronized clock produces an `unverified_time` result.
3. Coordinates omitted produces no location fields.
4. Coordinates supplied records consent, source, and accuracy.
5. Signed envelope verifies after simulated delivery.
6. Altering timestamp, coordinates, recipient, text, or media digest causes signature verification to fail.
7. Logs contain transaction IDs and outcomes only, with no private keys, passphrases, plaintext, or exact coordinates.
