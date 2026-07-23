#!/usr/bin/env python3

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

OUT = ROOT / "data/registry/timezones.json"

zone_tab = Path("/usr/share/zoneinfo/zone.tab")

records = []

for line in zone_tab.read_text().splitlines():

    if not line or line.startswith("#"):
        continue

    parts = line.split("\t")

    if len(parts) < 3:
        continue

    countries = parts[0].split(",")
    zone = parts[2]

    for country in countries:
        records.append(
            {
                "iana_name": zone,
                "country": country,
                "dst_supported": None
            }
        )


OUT.write_text(
    json.dumps(
        {
            "schema_version": "1.0",
            "source": "IANA TZDB (system zone.tab)",
            "timezones": records
        },
        indent=2
    )
)

print(f"Generated {len(records)} country timezone records")
