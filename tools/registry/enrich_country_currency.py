#!/usr/bin/env python3

import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

COUNTRIES = ROOT / "data/registry/countries.json"
CURRENCY_XML = Path("/usr/share/xml/iso-codes/iso_4217.xml")

currency_map = {}

tree = ET.parse(CURRENCY_XML)
root = tree.getroot()

for entry in root.findall("iso_4217_entry"):

    currency = entry.attrib.get("alpha_3_code")
    countries = entry.attrib.get("country")

    if not currency or not countries:
        continue

    for country in countries.split(","):

        currency_map[country.strip()] = currency


data = json.loads(
    COUNTRIES.read_text()
)


for country in data["countries"]:

    alpha2 = country["iso_alpha2"]

    country["currency"] = currency_map.get(alpha2)


COUNTRIES.write_text(
    json.dumps(data, indent=2)
)


print(
    "Currency enrichment complete"
)
