# WW.CX Digital Archive architecture

Status: source architecture and private deployment foundations prepared; live service activation remains separately gated.

## Authority model

One retained record has one authoritative durable home. Indexes, OCR databases, search engines, working copies and AI knowledge records are references or derivatives, not parallel authorities.

- **Google Drive / designated durable archive hierarchy** — canonical retained business/document evidence by subject when that system is designated authoritative for the record.
- **GitHub** — authoritative maintained source code, schemas, runbooks and sanitized engineering documentation.
- **Dropbox** — transitional/archive/reference system unless a record is explicitly designated otherwise.
- **WW.CX private archive storage** — authoritative retained copies for material deliberately ingested into the WW.CX archive, with SHA-256 provenance/register controls.
- **Paperless-ngx** — OCR, classification, document workflow and search over controlled working copies.
- **ArchiveBox** — private web capture and replay working/archive layer.
- **Omeka S** — curated catalog/exhibition/publication layer; metadata presentation is not the original evidence authority.
- **Zotero** — bibliographic/research metadata and citation workspace.
- **Internet Archive / Open Library** — external reference/archive/catalog integrations; never assumed authoritative for internal originals.
- **Cookie Monster** — ingestion, normalization, extraction, analysis, knowledge synthesis, provenance and review visibility.
- **Big Bird** — operational/orchestration control plane; it does not become the archive.

## Data flow

```text
Authoritative originals / explicitly staged copies
              |
              v
       Cookie Monster intake
  hash -> normalize -> extract -> analyze
              |
       +------+-------+
       |              |
       v              v
  Paperless       ArchiveBox
 document/OCR     web capture
       |              |
       +------+-------+
              v
   provenance-linked knowledge
              |
       human review boundary
              |
       +------+-------+
       |              |
       v              v
    Big Bird        Omeka S
 orchestration      curated view
              |
              v
   external reference links
 Zotero / Open Library / Internet Archive
```

## Mandatory controls

1. SHA-256 before transformation when an original is retained.
2. Exact duplicate decisions use hashes, never filename similarity alone.
3. Preserve original source pointer, acquisition timestamp/method and authority designation.
4. Derivatives must point back to source asset identity.
5. AI-generated knowledge remains reviewable and non-authoritative until human-approved where approval is required.
6. No archive credential is delegated to Fengus.
7. External publication/upload is separate from internal ingestion.
8. Public routing, DNS, certificates and authentication are separate activation changes.
9. Backups are tested as restore procedures, not merely copied files.
10. Service databases and indexes are rebuildable working state unless explicitly promoted to retained evidence.

## Initial private service placement

- Edge1 Paperless-ngx: `127.0.0.1:8113`
- Edge1 ArchiveBox: `127.0.0.1:8114`
- Business159 Omeka S: isolated cPanel application/document root with a dedicated database; no domain/DNS creation is implied by this source architecture.

Ports must be rechecked immediately before live deployment.

## Current source baselines

- Paperless-ngx `3.0.5`, pinned rather than `latest`.
- ArchiveBox `0.7.4`, the stable line selected instead of the 0.9.x release-candidate line.
- Omeka S `4.2` current supported line for Business159 planning.

Version pins must be rechecked against official release/security guidance before a live install.
