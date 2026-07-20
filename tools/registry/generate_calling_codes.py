#!/usr/bin/env python3

import csv
import json
from pathlib import Path

import phonenumbers
from phonenumbers.phonenumberutil import COUNTRY_CODE_TO_REGION_CODE

ROOT = Path(__file__).resolve().parents[2]
CSV_OUT = ROOT / "data/registry/sources/itu-e164/e164.csv"
JSON_OUT = ROOT / "data/registry/calling_codes.json"

records = []

for calling_code, regions in sorted(COUNTRY_CODE_TO_REGION_CODE.items()):
    code = f"+{calling_code}"

    for region in sorted(set(regions)):
        # "001" identifies non-geographic/global network services.
        records.append(
            {
                "country": region,
                "calling_code": code,
                "region": (
                    "GLOBAL_SERVICE"
                    if region == "001"
                    else "NANPA"
                    if calling_code == 1
                    else ""
                ),
                "status": "assigned",
            }
        )

CSV_OUT.parent.mkdir(parents=True, exist_ok=True)

with CSV_OUT.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(
        handle,
        fieldnames=["country", "calling_code", "region", "status"],
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(records)

JSON_OUT.write_text(
    json.dumps(
        {
            "schema_version": "1.0",
            "source": {
                "standard": "ITU-T E.164",
                "normalized_with": "python-phonenumbers",
                "phonenumbers_version": phonenumbers.__version__,
            },
            "calling_codes": records,
        },
        indent=2,
        ensure_ascii=False,
    )
    + "\n",
    encoding="utf-8",
)

print(f"Generated {len(records)} country/calling-code assignments")
print(f"Distinct calling codes: {len({r['calling_code'] for r in records})}")
