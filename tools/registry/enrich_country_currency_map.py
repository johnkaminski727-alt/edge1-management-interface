#!/usr/bin/env python3

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

COUNTRIES = ROOT / "data/registry/countries.json"
CURRENCIES = ROOT / "data/registry/currencies.json"

countries = json.loads(COUNTRIES.read_text())
currencies = json.loads(CURRENCIES.read_text())

mapping = {
    item["country"]: item["currency"]
    for item in currencies["currencies"]
}

updated = 0

for country in countries["countries"]:
    code = country["iso_alpha2"]

    if code in mapping:
        country["currency"] = mapping[code]
        updated += 1


COUNTRIES.write_text(
    json.dumps(countries, indent=2)
)

print(
    f"Updated {updated} country currency mappings"
)
