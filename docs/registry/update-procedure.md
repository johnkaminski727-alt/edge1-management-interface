# Country Registry Update Procedure

## Purpose

The WW.CX registry provides a shared reference for country identity, calling codes, geographic metadata, and time zones.

## Authoritative Sources

- ISO 3166 for country identifiers
- ITU E.164 for international calling codes
- IANA Time Zone Database for timezone rules
- ISO 4217 for currencies
- Unicode CLDR for regional formatting metadata

## Update Workflow

1. Import updated source data.
2. Run registry validation.
3. Review generated changes.
4. Commit the registry update.
5. Update integration consumers as required.

## Validation Requirements

- No duplicate ISO identifiers.
- No missing timezone identifiers.
- Calling codes must use E.164 format.
- Country references must resolve consistently.
