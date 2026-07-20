#!/usr/bin/env python3

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SOURCE = ROOT / "data/registry/sources/itu-e164/e164.csv"
OUTPUT = ROOT / "data/registry/calling_codes.json"


if not SOURCE.exists():
    raise SystemExit(
        f"Missing source: {SOURCE}"
    )


records = []

with SOURCE.open() as f:

    reader = csv.DictReader(f)

    for row in reader:
        records.append(
            {
                "country": row["country"],
                "calling_code": row["calling_code"],
                "region": row.get("region", ""),
                "status": row.get("status", "assigned")
            }
        )


OUTPUT.write_text(
    json.dumps(
        {
            "schema_version": "1.0",
            "source": "ITU E.164",
            "calling_codes": records
        },
        indent=2
    )
)

print(
    f"Imported {len(records)} E.164 allocations"
)
