# WW.CX Records Metadata and Naming Profile

## Required metadata

Every declared official record or archival package must carry, directly or through an associated manifest, the following metadata:

- record identifier;
- title;
- creator or responsible agent;
- business owner;
- creation date and time in UTC;
- last modification date and time in UTC;
- record class;
- business function or project;
- sensitivity classification;
- retention rule and trigger;
- authoritative-copy location;
- format and media type;
- checksum algorithm and value;
- source or provenance;
- related records and superseded versions;
- rights or access restrictions;
- preservation and disposition status.

Recommended additional fields include software version, environment, language, geographic scope, approval reference, Git commit SHA, pull-request number, and external persistent identifiers such as ORCID or DOI.

## Identifiers

Record identifiers must be unique, stable, and never reassigned. The preferred form is:

```text
WWCX-<FUNCTION>-<YYYYMMDD>-<SEQUENCE>
```

Example:

```text
WWCX-EDGE1-20260718-0001
```

Archival package identifiers should append a package revision:

```text
WWCX-EDGE1-20260718-0001-AIP-v1
```

## File naming

Use lowercase ASCII, hyphen-separated names without spaces. Dates use `YYYYMMDD`; timestamps use UTC in `YYYYMMDDTHHMMSSZ` form.

Preferred pattern:

```text
<record-class>-<subject>-<date-or-timestamp>-<version>.<extension>
```

Example:

```text
change-record-private-library-wrapper-20260718-v1.md
```

Do not encode secrets, personal data, access tokens, or unnecessary host details in file names.

## Sensitivity classes

- **Public:** approved for unrestricted publication.
- **Internal:** routine non-public business information.
- **Confidential:** information requiring limited role-based access.
- **Restricted:** secrets, credentials, private records, regulated information, security-sensitive configuration, or incident evidence.

Public repositories may contain only material classified Public. Sanitized derivatives must be treated as separate records linked to their restricted source record without exposing restricted metadata.

## Time and provenance

All operational timestamps must be recorded in UTC, with the originating system and agent identified. A record derived from another object must preserve a provenance link to the source and describe the transformation performed.

## Versioning

Git history may provide working-version control, but designated archival versions must also be captured in a preservation package with a manifest and checksums. Supersession does not authorize deletion unless the retention schedule and disposition process permit it.
