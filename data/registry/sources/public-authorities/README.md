# Public authority registry sources

This directory records the authoritative public datasets used to enrich and validate the WW.CX geographic and telecommunications registry.

## Source precedence

- **UN M49** is the preferred public backbone for country and area names, ISO alpha-2/alpha-3 identifiers, M49 numeric identifiers, and geographic groupings.
- **Statistics Canada SCCAI** is a secondary validation and Canadian naming source. Its historical dataset may supplement validity periods and change notes.
- **ITU E.164** remains authoritative for international calling-code assignments and shared/global-service codes.
- **IANA TZDB** remains authoritative for timezone identifiers, aliases, country mappings, and historical transitions.
- **IANA Root Zone Database** is authoritative for ccTLD and IDN ccTLD delegation information.
- **IANA Language Subtag Registry** validates region subtags and deprecated/preferred values.
- **Unicode CLDR** supplies localized display metadata only; it must not overwrite canonical legal or statistical names.

## Inclusion workflow

1. Save an unmodified source artifact beneath `data/registry/sources/<source-id>/`.
2. Record retrieval time, source URL, media type, byte size, and SHA-256 digest in that source's metadata file.
3. Parse into a source-specific normalized file; never write directly into the canonical registry during parsing.
4. Validate identifiers, uniqueness, row counts, and cross-source differences.
5. Merge through an explicit enrichment step that follows `source-manifest.json` precedence.
6. Regenerate the registry manifest, database, snapshots, and validation evidence.

## Safety and licensing

Only source artifacts whose reuse terms permit local processing and repository inclusion may be committed. When redistribution terms are uncertain, commit the importer, source metadata, checksums, and retrieval instructions, but not the downloaded artifact.

The manifest is configuration, not proof that a source artifact has been downloaded or successfully ingested. A source becomes active only after its artifact, normalized output, validation evidence, and generated registry changes are present.
