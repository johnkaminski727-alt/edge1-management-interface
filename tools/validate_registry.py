#!/usr/bin/env python3
"""Validate WW.CX country, calling-code, and timezone registry data."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data" / "registry"


def load(name):
    with open(REGISTRY / name, encoding="utf-8") as handle:
        return json.load(handle)


def main():
    countries = load("countries.json")
    timezones = load("timezones.json")
    calling_codes = load("calling_codes.json")

    assert isinstance(countries, list)
    assert isinstance(timezones, list)
    assert isinstance(calling_codes, list)

    iso_codes = [item["iso_alpha2"] for item in countries]
    assert len(iso_codes) == len(set(iso_codes)), "duplicate ISO country codes"

    for country in countries:
        assert country["iso_alpha2"]
        assert country["country_name"]

    for zone in timezones:
        assert zone["iana_name"]
        assert zone["country_iso"]

    for code in calling_codes:
        assert code["country_iso"]
        assert code["calling_code"].startswith("+")

    print("Registry validation passed")


if __name__ == "__main__":
    main()
