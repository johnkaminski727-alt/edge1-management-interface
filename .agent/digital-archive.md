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

## Source validation

The foundation regression package checks exact image pins, loopback-only web binds, Paperless secret-file configuration, ArchiveBox private defaults, authority separation, external credential exclusion and Big Bird retirement/live-acceptance rules.

## Remaining live gates

1. Verify/install a container runtime on Edge1 before Paperless/ArchiveBox activation.
2. Create runtime secrets outside Git.
3. Validate storage capacity/backup/restore and recheck ports immediately before apply.
4. Perform Business159 Omeka database/filesystem setup through an authenticated host path.
5. Complete Zotero interactive login/challenge when needed; do not request credentials in chat.
6. Treat Internet Archive uploads and any public Omeka/Edge1 routing as separate external/publication actions.
7. Do not make DNS/certificate/authentication/public-route changes as part of private service installation.
