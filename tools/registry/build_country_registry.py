#!/usr/bin/env python3

import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
REG = ROOT / "data" / "registry"


def load(name):
    with open(REG / name) as f:
        return json.load(f)


def main():

    countries = load("countries.json")["countries"]
    calling_codes = load("calling_codes.json")["calling_codes"]
    timezones = load("timezones.json")["timezones"]
    currencies = load("currencies.json")["currencies"]

    registry = {}

    for c in countries:
        iso = c["iso_alpha2"]

        registry[iso] = {
            "iso_alpha2": iso,
            "iso_alpha3": c.get("iso_alpha3"),
            "name": c.get("name"),
            "calling_codes": list(c.get("calling_codes", [])),
            "timezones": list(c.get("timezones", [])),
            "currency": c.get("currency")
        }


    for item in calling_codes:
        country = item.get("country")

        if country in registry:
            code = item.get("calling_code")

            if code and code not in registry[country]["calling_codes"]:
                registry[country]["calling_codes"].append(code)


    for item in timezones:
        country = item.get("country")

        if country in registry:
            tz = item.get("iana_name")

            if tz and tz not in registry[country]["timezones"]:
                registry[country]["timezones"].append(tz)


    for item in currencies:
        country = item.get("country")

        if country in registry:
            registry[country]["currency"] = item.get("currency")


    output = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_standards": [
            "ISO 3166",
            "ITU E.164",
            "NANPA",
            "IANA TZDB",
            "ISO 4217"
        ],
        "countries": sorted(
            registry.values(),
            key=lambda x: x["iso_alpha2"]
        )
    }


    with open(REG / "country_registry.json", "w") as f:
        json.dump(output, f, indent=2)


    print("Generated country_registry.json")
    print("countries:", len(output["countries"]))


if __name__ == "__main__":
    main()
