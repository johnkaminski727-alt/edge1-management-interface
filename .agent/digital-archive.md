# WW.CX Digital Archive

Last updated: 2026-08-22

## Source-ready architecture

- Canonical evidence authority remains separate from indexes, OCR stores and AI knowledge.
- Paperless-ngx is the private document processing/OCR/search layer.
- ArchiveBox is the private web-capture layer.
- Omeka S is the curated catalog/publication layer.
- Zotero, Open Library and Internet Archive are external research/catalog/archive integrations.
- Cookie Monster owns ingestion/provenance/knowledge synthesis; Big Bird stays the operations/orchestration plane.

## Private deployment baselines

- Paperless-ngx pinned to 3.0.5 and loopback `127.0.0.1:8113`.
- ArchiveBox pinned to stable 0.7.4 and loopback `127.0.0.1:8114` with public views/add and automatic Archive.org submission disabled.
- Omeka S current 4.2 line targets Business159 after dedicated DB/secret/private-routing preparation.
- `deploy/digital-archive/edge1_private_foundation.py` provides the bounded Paperless/ArchiveBox Edge1 bootstrap transaction: read-only preflight by default, root-only apply, no container-runtime installation, no canonical ingestion, no public route, evidence capture, loopback health verification and volume-preserving rollback.
- Private bootstrap requires Docker + Compose to already exist, Paperless runtime secret files outside Git, and at least 5 GiB free storage. Missing runtime/secrets/storage are blockers, not permission for the transaction to broaden authority.
- `deploy/digital-archive/omeka/business159_omeka_deploy.py` provides a bounded shared-host Omeka S 4.2.x private-file transaction. It validates PHP/extensions, thumbnail support, a deterministic extracted-release tree hash, private `database.ini`, storage and pointer safety; apply copies only into the isolated app tree and rollback moves only the release pointer.
- The Omeka transaction intentionally cannot create the database/user or first administrator, modify `public_html`, or change DNS/certificates/Apache/authentication/public routing. Shared-host rewrite/AllowOverride remains explicitly unverified until live control-plane/browser acceptance.

## Source validation

The foundation regression package checks exact image pins, loopback-only web binds, Paperless secret-file configuration, ArchiveBox private defaults, authority separation, external credential exclusion and Big Bird retirement/live-acceptance rules.

The private Edge1 bootstrap regression additionally verifies Compose source policy, secret-file permissions/symlink rejection, read-only blocked preflight behavior, absence of secret content/path leakage, canonical repo restriction, rollback-path containment, automatic reverse-order rollback, and explicit absence of Docker installation/public-routing/volume-deletion authority.

The Business159 Omeka regression verifies 4.2.x release structure/tree integrity, payload symlink rejection, database.ini secrecy/permissions, read-only preflight, explicit rewrite-policy uncertainty, isolated release deployment, pointer-only rollback, and absence of database/admin/public mutation authority.

## Remaining live gates

1. Attach an authenticated write-capable Edge1 path; the currently published Edge1 Operator remains read-only.
2. Verify/install a container runtime on Edge1 before Paperless/ArchiveBox activation. The private bootstrap script intentionally cannot install it.
3. Create Paperless runtime secrets outside Git and pass only their host-side paths to preflight/apply.
4. Validate Paperless/ArchiveBox backup/restore before canonical document ingestion; the bootstrap does not ingest canonical records.
5. Reconnect an authenticated Business159 host/browser path, recheck PHP/rewrite/upload limits, create the dedicated Omeka database/user without exposing credentials, and run the private Omeka file transaction against the reviewed 4.2.x payload.
6. Complete Omeka first-user setup interactively, then verify PHP CLI/background jobs, thumbnails, uploads and backup/restore before any public route.
7. Complete Zotero interactive login/challenge when needed; do not request credentials in chat.
8. Treat Internet Archive uploads and any public Omeka/Edge1 routing as separate external/publication actions.
9. Do not make DNS/certificate/authentication/public-route changes as part of private service installation.
