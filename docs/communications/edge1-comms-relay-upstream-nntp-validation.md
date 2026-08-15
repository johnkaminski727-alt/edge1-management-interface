# Edge1 Upstream NNTP Validation Plan

Date: 2026-08-15

## Repository gate

Before merge:

- compile and execute the scripted no-network NNTP validation;
- run the complete repository validation workflow;
- run Edge1 Operator Validation;
- require a clean mergeable PR;
- confirm no credentials, database copies, or live config files are committed.

## Live activation gate

Repository merge does not enable an upstream source.

When reader credentials exist, activation must be attended and proceed in this order:

1. verify Edge1 repository and relay health;
2. back up `/etc/wwcx/comms-relay.json` and the relay SQLite database;
3. install the protected credential file without displaying its contents;
4. add exactly the reviewed disabled/allowlisted NNTP mappings to a candidate config;
5. validate and diff the candidate;
6. run `ingest run --dry-run` against the candidate over TLS;
7. verify candidate article count, target groups, source Message-IDs and size bounds;
8. apply the candidate and restart only the relay;
9. verify IRC, NNTP, control, telephony and loopback listener health;
10. verify imported articles and provenance;
11. immediately rerun ingestion and require zero duplicate creations;
12. record sanitized evidence and update the acceptance/state records.

If any post-apply verification fails, restore the previous relay config and restart the relay. Already imported articles should be preserved unless a separate reviewed cleanup is explicitly authorized; the source ledger prevents duplicate re-import on a later retry.

## Provenance-aware article accounting

Do not validate an imported local group by assuming every article in that group belongs to the external NNTP source.

Other approved relay sources can legitimately post to the same group. In particular, `wwcx-bootstrap` creates a one-time group introduction when it discovers a new group.

For an imported group, classify and count articles by ingestion provenance:

- external items: match the configured external `source_name` and verify unique upstream `source_item_id` values;
- bootstrap introduction: if present, match `source_name=wwcx-bootstrap` and source item ID `<group>:v1`;
- any additional provenance class must be explicitly understood before acceptance.

The accepted `usenet.comp.lang.python` activation demonstrated the expected case:

- 8 `eternal.comp.lang.python` items;
- 1 `wwcx-bootstrap` introduction (`usenet.comp.lang.python:v1`);
- 0 duplicate Eternal September source IDs;
- 9 total local-group articles.

Therefore `group_article_count == external_source_ledger_count` is not a valid general invariant. Validate source-specific ledger counts, duplicate identity, target-group membership, provenance headers, and any independently approved local articles instead.

## Repository movement during attended activation

Do not chase a rapidly advancing remote `main` during a config-only activation if unrelated workstreams are merging concurrently.

Instead:

1. freeze the clean local checkout revision at the start of the attended operation;
2. require the validated implementation floor to be an ancestor of that local revision;
3. diff protected Communications Relay paths between the implementation floor and the frozen local revision;
4. stop if protected relay paths changed unexpectedly;
5. otherwise perform the bounded config-only activation against that frozen, tested checkout.

Record both the frozen live checkout revision and the later documentation branch/base revision separately when they differ.

## Deferred gates

The following are not authorized by this implementation:

- sending a peering request;
- inbound NNTP feed acceptance;
- server-to-server streaming;
- DNS or firewall changes;
- public Edge1 IRC/NNTP exposure;
- forwarding WW.CX articles upstream.

Reader-account creation and credential installation are operational prerequisites performed outside the repository and must never place credential values in committed files or shared evidence.
