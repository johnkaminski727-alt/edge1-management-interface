#!/usr/bin/env python3

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

COUNTRIES = ROOT / "data/registry/countries.json"
TIMEZONES = ROOT / "data/registry/timezones.json"

countries = json.loads(COUNTRIES.read_text())
zones = json.loads(TIMEZONES.read_text())

mapping = {}

for tz in zones["timezones"]:
    country = tz.get("country")

    if country:
        mapping.setdefault(country, []).append(
            tz["iana_name"]
        )

for country in countries["countries"]:
    code = country["iso_alpha2"]

    country["timezones"] = sorted(
        mapping.get(code, [])
    )

COUNTRIES.write_text(
    json.dumps(countries, indent=2)
)

print(
    "Timezone enrichment complete"
)
