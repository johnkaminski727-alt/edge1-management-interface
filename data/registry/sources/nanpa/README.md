# NANPA NPA source

`raw/npa_report.csv` is the downloaded NANPA NPA Database source.

Normalize and import it with:

    python3 tools/registry/normalize_nanpa.py
    python3 tools/registry/import_nanpa.py

The normalized registry is `data/registry/nanpa_npa.csv`.

The `timezone` field preserves NANPA published timezone codes such as E, C, M, P, EC, and CM. These are not exact IANA timezone identifiers.

Status values are derived as active, assigned, reserved, available, or unavailable.

Records without a country assignment use pseudo-region code `001`.
