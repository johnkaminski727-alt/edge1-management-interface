#!/usr/bin/env python3

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SOURCE = ROOT / "data/registry/sources/itu-e164/raw/e164.txt"
OUTPUT = ROOT / "data/registry/sources/itu-e164/e164.csv"

text = SOURCE.read_text(errors="ignore")

# Extract the numerical-order section only
start = text.find(
    "List of ITU-T Recommendation E.164 assigned country codes - numerical order"
)

end = text.find(
    "List of ITU-T Recommendation E.164 assigned country codes - alphabetical order"
)

section = text[start:end]

lines = [
    x.strip()
    for x in section.splitlines()
    if x.strip()
]

records = []

# Known two-column table pattern:
# numeric code line followed by country line
for i in range(len(lines)-1):

    code = lines[i]
    country = lines[i+1]

    if re.fullmatch(r"\d{1,3}", code):

        if (
            country.startswith("Spare code")
            or country.startswith("Reserved")
            or country.startswith("Telecommunications")
            or country.startswith("Universal")
        ):
            continue

        records.append(
            {
                "calling_code": "+" + code,
                "country_name": country,
                "region": "",
                "status": "assigned"
            }
        )


with OUTPUT.open("w", newline="") as f:

    writer = csv.DictWriter(
        f,
        fieldnames=[
            "country",
            "calling_code",
            "region",
            "status"
        ]
    )

    writer.writeheader()

    for r in records:

        writer.writerow(
            {
                "country": r["country_name"],
                "calling_code": r["calling_code"],
                "region": r["region"],
                "status": r["status"]
            }
        )


print(
    f"Generated {len(records)} E.164 records"
)
