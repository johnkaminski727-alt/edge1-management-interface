# Edge1 Communications Relay / Upstream NNTP / News Reader Closeout

Date: 2026-08-17  
Classification: sanitized operational closeout and archive-preparation record  
System: `edge1.ww.cx`  
Repository: `johnkaminski727-alt/edge1-management-interface`

## Archive status

**Prepared, not yet sealed.**

Repository history, sanitized acceptance records, evidence-root references, exclusions, and the production checkout boundary are reconciled. Final archive sealing still requires a fresh host-side SHA-256 inventory of the retained protected evidence and confirmation of the exact News Reader v2 evidence directory.

No source evidence should be moved, deleted, compressed, or pruned merely because this closeout exists.

## Accepted production scope

The closeout covers:

1. private Edge1 IRC/NNTP Communications Relay;
2. founder/local identity activation;
3. automatic bootstrap and Edge1 repository ingestion;
4. selective outbound Eternal September NNTP reader integration;
5. accepted `comp.lang.python` mapping;
6. accepted `news.admin.peering` mapping;
7. private read-only News Reader v2;
8. repository reconciliation and durable state documentation.

It does not cover public protocol exposure, inbound NNTP feeds, formal peering, upstream posting, DNS/firewall/certificate changes, or forwarding private `wwcx.*` articles upstream.

## Repository chain of custody

Important repository milestones:

- upstream NNTP implementation floor: `c7b4b2c9124e072abaa356f0645e10d449c38eea`;
- News Reader validated development head: `b06233c0ce2210b58f9fe88ccb2b64cd14a959f6`;
- News Reader production deployment head: `974c7141e18deac92671f81fb1bd3c3ed02a6c68`;
- clean News Reader integration PR: #341;
- PR #341 merge commit: `6a0397a7f39c07afa3a779c0578e06d165df41e8`;
- durable state PR: #342;
- PR #342 merge commit: `1c115663fb23de82e51fcfd0520d91fa196261be`;
- PR #337: closed as superseded development history, not merged.

The documentation/archive-preparation PR created from this closeout should be recorded here after merge as the final repository seal point for the documentation set.

## Production checkout boundary

The accepted News Reader production checkout is intentionally not the same thing as current remote `main`:

- branch: `deploy/private-nntp-news-reader-v2-20260817`;
- head: `974c7141e18deac92671f81fb1bd3c3ed02a6c68`;
- result: `NEWS_READER_V2_DEPLOYMENT=PASS`.

Remote `main` also contains unrelated time-authority work. Do not update the live Edge1 checkout merely to make it resemble repository history. Any later production reconciliation must be reviewed and validated as its own change.

## Protected evidence source ledger

The following known Edge1 evidence roots must be preserved as archive sources:

| Source key | Purpose | Protected path | Disposition |
| --- | --- | --- | --- |
| `COMMS-DEPLOY-20260815-183129` | Initial relay deployment | `/var/lib/wwcx-deployment-evidence/comms-relay/20260815T183129Z` | retain |
| `COMMS-FOUNDER-20260815-183745` | Founder-account activation | `/var/lib/wwcx-deployment-evidence/comms-relay/founder-account-20260815T183745Z` | retain |
| `COMMS-INGEST-ACT-20260815-191918` | Automatic-ingestion activation | `/var/lib/wwcx-deployment-evidence/comms-relay/auto-ingest-20260815T191918Z` | retain |
| `COMMS-INGEST-CODE-20260815-191922` | Automatic-ingestion code deployment | `/var/lib/wwcx-deployment-evidence/comms-relay/20260815T191922Z` | retain |
| `COMMS-ES-PYTHON-20260815-233435` | Eternal September `comp.lang.python` activation | `/var/lib/wwcx-deployment-evidence/comms-relay/eternal-september-live-20260815T233435Z` | retain |
| `COMMS-ES-PEERING-PREP-20260816-001246` | Second-source candidate, backups and TLS dry run | `/var/lib/wwcx-deployment-evidence/comms-relay/eternal-news-admin-peering-prep-20260816T001246Z` | retain |
| `COMMS-ES-PEERING-RECOVERY-20260816-002007` | Guarded failed activation/recovery evidence | `/var/lib/wwcx-deployment-evidence/comms-relay/eternal-news-admin-peering-live-20260816T002007Z` | retain as failed-attempt history if present |
| `COMMS-ES-PEERING-LIVE-20260816-005124` | Accepted second-source activation | `/var/lib/wwcx-deployment-evidence/comms-relay/eternal-news-admin-peering-live-20260816T005124Z` | retain |
| `COMMS-NEWS-READER-V2` | News Reader v2 deployment/acceptance | exact protected path not re-read during repository closeout | **reconcile before seal** |

The archive source ledger is intentionally explicit about the one unresolved path rather than inventing it.

## Live state that should be captured by hash, not copied into Git

Before archive sealing, record SHA-256 and metadata for:

- `/etc/wwcx/comms-relay.json` — live canonical config;
- `/var/lib/wwcx-comms/comms.sqlite3` — live relay SQLite database;
- `/var/lib/wwcx-comms/config-control/` — candidate/apply/rollback metadata and retained backups relevant to the activation history;
- each retained evidence file under the source-ledger roots above.

The SQLite database may contain durable article bodies, local identity state, password-derivation material, and other private operational data. It is a restricted archive object and must not be committed to Git.

## Explicit exclusions

Never include these in the repository archive or general-purpose evidence bundle:

- `/etc/wwcx/credentials/eternal-september.json` contents;
- Eternal September username/password values;
- plaintext passwords or authentication transcripts;
- private keys, tokens, cookies, or unrelated credentials;
- raw account password hashes or database extracts intended only for operational recovery;
- unrelated Edge1 evidence trees;
- public claims that successful reader pulling constitutes formal NNTP peering.

Credential metadata such as owner/group/mode may be recorded without reading credential values.

## Sanitized repository records to retain

Living and acceptance documentation:

- `docs/communications/README.md`;
- `docs/communications/edge1-comms-relay-architecture.md`;
- `docs/communications/edge1-comms-relay-ingestion.md`;
- `docs/communications/edge1-comms-relay-upstream-nntp.md`;
- `docs/communications/edge1-comms-relay-upstream-nntp-validation.md`;
- `docs/communications/edge1-comms-relay-news-reader.md`;
- `docs/handoff/edge1-comms-relay-runbook.md`;
- `docs/communications/edge1-comms-relay-live-acceptance-20260815.md`;
- `docs/communications/edge1-comms-relay-ingestion-live-acceptance-20260815.md`;
- `docs/communications/edge1-comms-relay-upstream-nntp-live-acceptance-20260815.md`;
- `docs/communications/edge1-comms-relay-upstream-nntp-second-source-live-acceptance-20260816.md`;
- `docs/communications/edge1-comms-relay-news-reader-live-acceptance-20260817.md`;
- `.agent/comms-relay.md`;
- `.agent/comms-relay-upstream-nntp.md`;
- this closeout record.

Historical acceptance records should remain unchanged except for later correction records when a factual error is discovered. Do not rewrite history simply to make all dated files read like the current system.

## Host-side archive sealing procedure

Run only from an authenticated Edge1 session after confirming the live service remains healthy. Do not display file contents.

1. Resolve the exact News Reader v2 evidence root from retained deployment evidence.
2. Enumerate every file under the protected source-ledger roots.
3. Record path, size, mode, owner/group, modification time, and SHA-256 for each retained file.
4. Hash the live config and SQLite database without copying them into the repository.
5. Verify that the Eternal September credential file is absent from the inventory payload except for metadata-only exclusion evidence if desired.
6. Reconcile counts: source roots, files, retained files, unavailable paths, exact duplicates by hash, and errors.
7. Write the final manifest into a new protected archive-preparation evidence directory under `/var/lib/wwcx-deployment-evidence/comms-relay/`.
8. Re-run the inventory and require idempotent totals with no unexplained new duplicate records.
9. Update this record with the final manifest path and SHA-256, then merge that documentation-only seal update.

## Archive completion gate

Do not mark the Communications Relay archive **sealed** until all are true:

- exact News Reader v2 evidence path resolved;
- all listed evidence roots checked for existence or explicitly marked unavailable;
- every retained file has a SHA-256;
- live config and SQLite metadata/hash captured without credential disclosure;
- exact duplicates distinguished from materially different versions;
- final totals reconcile;
- manifest rerun is idempotent;
- final documentation PR is merged;
- no production checkout or service change was made solely for archival housekeeping.

## Resume point

If archive sealing is deferred, resume from this record. The next safe action is a read-only Edge1 evidence inventory and SHA-256 manifest over the source-ledger paths above. No production service change is required.