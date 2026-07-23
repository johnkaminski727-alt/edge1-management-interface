#!/usr/bin/env python3

import json
import icu
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

COUNTRIES = ROOT / "data/registry/countries.json"
OUT = ROOT / "data/registry/currencies.json"

countries = json.loads(
    COUNTRIES.read_text()
)

records = []

for country in countries["countries"]:

    code = country["iso_alpha2"]

    try:
        locale = icu.Locale(f"en_{code}")

        fmt = icu.NumberFormat.createCurrencyInstance(locale)

        symbol = fmt.getCurrency()

        if symbol:
            records.append(
                {
                    "country": code,
                    "currency": symbol
                }
            )

    except Exception:
        pass


OUT.write_text(
    json.dumps(
        {
            "schema_version": "1.0",
            "source": "ICU CLDR locale currency mapping",
            "currencies": records
        },
        indent=2
    )
)

print(
    f"Generated {len(records)} currency mappings"
)
