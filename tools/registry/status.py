#!/usr/bin/env python3

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

FILES = {
    "calling_codes": ROOT / "data/registry/calling_codes.json",
    "countries": ROOT / "data/registry/countries.json",
    "timezones": ROOT / "data/registry/timezones.json",
}


for name, path in FILES.items():

    print("\n" + name)

    if not path.exists():
        print(" MISSING")
        continue

    data = json.loads(path.read_text())

    for key, value in data.items():
        if isinstance(value, list):
            print(f" {key}: {len(value)}")
