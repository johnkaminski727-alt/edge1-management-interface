#!/usr/bin/env python3

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REG = ROOT / "data" / "registry"


def main():

    with open(REG / "country_registry.json") as f:
        registry = json.load(f)

    countries = registry["countries"]

    errors = []
    warnings = []

    if not countries:
        errors.append("country_registry.json contains zero countries")


    seen = set()

    for c in countries:

        iso = c.get("iso_alpha2")

        if not iso:
            errors.append("Missing ISO alpha2")
            continue

        if iso in seen:
            errors.append(f"Duplicate ISO country {iso}")

        seen.add(iso)


        if not c.get("name"):
            errors.append(f"{iso}: missing name")

        if not c.get("calling_codes"):
            warnings.append(f"{iso}: no calling code assigned")


        if not c.get("timezones"):
            warnings.append(f"{iso}: no timezone assigned")


        if not c.get("currency"):
            warnings.append(f"{iso}: no currency assigned")


    if errors:
        print("Relationship validation FAILED")
        for e in errors:
            print("-", e)
        raise SystemExit(1)


    print("Relationship validation passed")
    print("country relationships:", len(countries))

    if warnings:
        print("\nWarnings:")
        for w in warnings:
            print("-", w)

    print("\nwarning count:", len(warnings))


if __name__ == "__main__":
    main()
