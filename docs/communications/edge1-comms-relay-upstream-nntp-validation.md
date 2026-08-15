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

## Deferred gates

The following are not authorized by this implementation:

- Eternal September account registration on the user's behalf;
- sending a peering request;
- inbound NNTP feed acceptance;
- server-to-server streaming;
- DNS or firewall changes;
- public Edge1 IRC/NNTP exposure;
- forwarding WW.CX articles upstream.
