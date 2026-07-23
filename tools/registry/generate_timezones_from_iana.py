#!/usr/bin/env python3

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SOURCE = ROOT / "data/registry/sources/iana-tz/extracted/zone1970.tab"
VERSION = ROOT / "data/registry/sources/iana-tz/extracted/version"

OUT = ROOT / "data/registry/timezones.json"


def read_version():
    if VERSION.exists():
        return VERSION.read_text().strip()
    return None


records = []

for line in SOURCE.read_text(encoding="utf-8").splitlines():

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
                "country": country,
                "iana_name": zone,
                "dst_supported": None
            }
        )


payload = {
    "schema_version": "1.0",
    "source": "IANA Time Zone Database",
    "source_version": read_version(),
    "timezones": records
}

OUT.write_text(
    json.dumps(payload, indent=2) + "\n",
    encoding="utf-8"
)

print(f"Generated {len(records)} timezone records")
print(f"TZDB version: {payload['source_version']}")
