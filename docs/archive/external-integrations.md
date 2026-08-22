# External archive and research integrations

## Open Library

Use for public bibliographic discovery and identifiers. Imported metadata must retain source URL/identifier and retrieval timestamp. Do not treat Open Library metadata as proof of internal document authenticity.

## Internet Archive

Use only for deliberately public/external archival material. Uploading WW.CX material is an external disclosure action and is never implied by internal Cookie Monster ingestion. Account verification/credentials remain outside repository state.

## Zotero

Use for citations, research collections, attachments or links where appropriate. Zotero metadata can feed Cookie Monster through an explicit connector/export boundary, but Zotero is not the authoritative home for WW.CX operational evidence unless a record is deliberately designated that way.

## Connector contract

External connector records should normalize to:

- provider;
- provider object/record identifier;
- canonical external URL when public;
- retrieval timestamp;
- content hash when bytes are retained;
- licensing/access notes;
- source authority classification;
- local authoritative record pointer when one exists.

No external account credential belongs in a knowledge record, archive register, Git repository, browser status snapshot or Fengus work item.
