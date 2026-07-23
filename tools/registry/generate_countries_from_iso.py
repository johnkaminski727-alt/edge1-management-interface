#!/usr/bin/env python3

import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SOURCE = Path("/usr/share/xml/iso-codes/iso_3166-1.xml")
OUT = ROOT / "data/registry/countries.json"

records = []

tree = ET.parse(SOURCE)
root = tree.getroot()

for country in root.findall("iso_3166_entry"):

    alpha2 = country.attrib.get("alpha_2_code")
    alpha3 = country.attrib.get("alpha_3_code")
    name = country.attrib.get("name")

    if not alpha2 or not name:
        continue

    records.append(
        {
            "iso_alpha2": alpha2,
            "iso_alpha3": alpha3,
            "name": name,
            "calling_codes": [],
            "timezones": [],
            "currency": None
        }
    )


payload = {
    "schema_version": "1.0",
    "source_standards": [
        "ISO 3166-1",
        "ITU E.164",
        "IANA TZDB",
        "ISO 4217"
    ],
    "countries": records
}


OUT.write_text(
    json.dumps(payload, indent=2)
)

print(
    f"Generated {len(records)} countries"
)
