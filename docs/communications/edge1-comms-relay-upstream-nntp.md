# Edge1 Communications Relay: Selective Upstream NNTP Pull

Date: 2026-08-15

## Purpose

Extend the private WW.CX Edge1 Communications Relay with a controlled outbound-only NNTP reader source. The source is designed to copy a small allowlisted set of public Usenet groups into a clearly separated local `usenet.*` namespace without enabling NNTP peering, inbound feeds, public listeners, or federation.

The initial reference provider is Eternal September. This is a reference integration only until an operator separately establishes reader credentials and explicitly activates one or more sources.

## External reference state

As checked on 2026-08-15 against Eternal September's public technical pages:

- reader service: `news.eternal-september.org`;
- authenticated NNRP is available on port 119 and TLS port 563;
- the separate transit/peering endpoint is `feeder.eternal-september.org` on port 433;
- formal peering lists prerequisites including a static IP, 24/7 availability, and Cleanfeed.

References:

- https://www.eternal-september.org/serverstatus.php?language=en
- https://www.eternal-september.org/index.php?showpage=peering
- https://www.eternal-september.org/index.php?showpage=faq

The WW.CX pull adapter deliberately targets the authenticated reader service, not the feeder service.

## Security boundary

The upstream reader implementation is outbound-only and requires TLS. It does not:

- listen on a new port;
- change DNS or firewall policy;
- accept incoming NNTP feeds;
- send WW.CX articles upstream;
- enable `IHAVE`, `CHECK`, `TAKETHIS`, streaming feeds, or server-to-server peering;
- create or transmit account credentials through the repository;
- automatically enumerate and mirror every upstream group.

Every source maps exactly one explicitly allowlisted upstream group to one local group. This provides separate enable/disable state, cursor, retention, scan budget, article-size limit, and audit/provenance identity for each mapping.

## Namespace policy

External groups should be mirrored beneath `usenet.*` rather than imported directly into the native WW.CX hierarchy. Examples:

- `comp.lang.python` -> `usenet.comp.lang.python`
- `news.admin.peering` -> `usenet.news.admin.peering`
- `news.software.nntp` -> `usenet.news.software.nntp`
- `news.software.readers` -> `usenet.news.software.readers`
- `comp.protocols.time.ntp` -> `usenet.comp.protocols.time.ntp`

This keeps `wwcx.*` authoritative for WW.CX-originated material while making the source of mirrored public discussion obvious to readers and operators.

## Article identity and provenance

For an imported article:

- the upstream Message-ID is the ingestion source-item ID and therefore the deduplication identity;
- WW.CX generates a deterministic local Message-ID rather than reusing the upstream Message-ID;
- the upstream author is preserved as the local displayed author;
- upstream group, server, Message-ID, article number, content type, date, and References are preserved in `X-WWCX-Upstream-*` headers when available;
- `X-WWCX-Automated`, `X-WWCX-Source`, and `X-WWCX-Source-ID` remain present through the common ingestion ledger.

The local deterministic Message-ID prevents an imported item from impersonating a native WW.CX article while the upstream Message-ID still provides exact deduplication and traceability.

## Content controls

The initial adapter accepts only single-part `text/*` articles. It rejects or skips:

- multipart MIME articles;
- non-text content types;
- articles without a syntactically valid upstream Message-ID;
- malformed header values;
- articles beyond the configured byte ceiling;
- unavailable or expired article numbers.

Each source has `initial_items`, `scan_limit`, and `max_article_bytes` bounds. The global ingestion `max_items_per_run` limit still applies.

## Cursor behavior

The local ingestion state stores the last scanned upstream article number independently for each source. Normal runs scan only newer article numbers. If the upstream high-water mark moves behind the local cursor, the source is treated as rewritten/reset and performs only the configured bounded initial lookback. The event is audited.

Deduplication uses the upstream Message-ID, so an article is not duplicated merely because an upstream server renumbers it.

## Credential handling

Credentials are not permitted in the relay JSON configuration. A source may reference an absolute JSON credential file containing:

```json
{
  "username": "operator-supplied-user",
  "password": "operator-supplied-password"
}
```

Recommended production location:

`/etc/wwcx/credentials/eternal-september.json`

Recommended ownership/mode:

`root:wwcx-comms 0640`

Do not commit the credential file, paste its contents into tickets or chat, or include it in deployment evidence. The sanitized relay configuration reports only whether a credential file is configured, not its path or values.

## Example disabled source

The repository example configuration includes a disabled Eternal September mapping for `comp.lang.python` to `usenet.comp.lang.python`. Enabling it is intentionally a separate attended activation step after credentials exist and a dry-run succeeds.

## Suggested initial cohort

Eternal September's public group listings showed current article activity on 2026-08-15 for several groups relevant to WW.CX operations and experimentation. A conservative first cohort would be:

1. `news.admin.peering` -> `usenet.news.admin.peering`
2. `news.software.nntp` -> `usenet.news.software.nntp`
3. `news.software.readers` -> `usenet.news.software.readers`
4. `comp.lang.python` -> `usenet.comp.lang.python`
5. `comp.protocols.time.ntp` -> `usenet.comp.protocols.time.ntp`

Add one mapping at a time and verify article quality, volume, retention, and abuse characteristics before expanding.

## Activation gate

Repository support can be merged without activating external access. Live activation remains blocked until all of the following are true:

1. an Eternal September reader account exists through a legitimate operator-created registration;
2. the credential file is installed on Edge1 without exposing its contents;
3. the chosen upstream groups are reviewed and explicitly allowlisted;
4. a pre-change SQLite/config backup is captured;
5. the candidate configuration validates and shows only the intended `nntp` source additions;
6. an attended `ingest run --dry-run` succeeds over TLS;
7. actual ingestion produces expected local groups/articles and provenance;
8. a repeat run proves idempotency;
9. IRC, local NNTP, control, telephony, and loopback listener safety remain healthy.

Formal server-to-server peering with Eternal September is a later and separate project. It must not be inferred from successful reader-mode pulling.
