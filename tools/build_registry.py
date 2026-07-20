#!/usr/bin/env python3
"""Build and validate Edge1 geographic registry artifacts."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data" / "registry"


def load(name):
    with (REGISTRY / name).open(encoding="utf-8") as handle:
        return json.load(handle)


def validate():
    countries = load("countries.json")
    seen = set()

    for country in countries:
        code = country.get("iso_alpha2")
        if not code:
            raise ValueError("country missing iso_alpha2")
        if code in seen:
            raise ValueError(f"duplicate country code: {code}")
        seen.add(code)

    return len(countries)


if __name__ == "__main__":
    count = validate()
    print(f"registry validation passed: {count} countries")
