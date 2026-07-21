# Country, Calling Code, Time Zone, and Geographic Registry 1.0

Status: complete for the canonical version 1.0 dataset and validation pipeline.

## Delivered dataset

The canonical generated artifact is `data/registry/country_registry.json`.

It contains 249 ISO 3166-1 country and territory records and joins:

- ISO 3166 alpha-2 and alpha-3 identifiers;
- English country or territory names;
- ITU E.164 calling codes, including shared numbering plans;
- IANA time-zone identifiers;
- ISO 4217 currency identifiers.

## Source artifacts

- `data/registry/countries.json`
- `data/registry/calling_codes.json`
- `data/registry/timezones.json`
- `data/registry/currencies.json`
- `data/registry/sources.json`
- `data/registry/registry-version.json`

## Build and validation

Rebuild the canonical artifact:

```sh
python3 tools/registry/build_country_registry.py
```

Validate relationships:

```sh
python3 tools/registry/validate_relationships.py
```

Run strict release tests:

```sh
python3 -m unittest tests.registry.test_registry_release
```

The GitHub Actions workflow `.github/workflows/registry-validation.yml` rebuilds the generated artifact, rejects an unreproducible diff, validates relationships, and runs the release tests.

## Expected unassigned values

The following ISO records legitimately have no independently assigned E.164 calling code in the normalized source data:

- AQ — Antarctica
- BV — Bouvet Island
- GS — South Georgia and the South Sandwich Islands
- HM — Heard Island and McDonald Islands
- PN — Pitcairn
- TF — French Southern Territories
- UM — United States Minor Outlying Islands

The following records have no directly assigned IANA country-zone entry:

- BV — Bouvet Island
- HM — Heard Island and McDonald Islands

These are warnings, not validation failures.

## Consumer contract

Consumers should use ISO alpha-2 as the stable primary key and treat calling codes and time zones as one-to-many relationships. UTC offsets must be calculated from IANA zone rules at the requested instant rather than stored as permanent country attributes.

## Maintenance

Future source refreshes must update source/version metadata, regenerate `country_registry.json`, pass relationship validation and release tests, and preserve the documented exceptions unless the authoritative standards change.
