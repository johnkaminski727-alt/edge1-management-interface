#!/usr/bin/env python3

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

FILES = {
    "calling_codes": ROOT / "data/registry/calling_codes.json",
    "countries": ROOT / "data/registry/countries.json",
    "timezones": ROOT / "data/registry/timezones.json",
}


def load(path):
    return json.loads(path.read_text())


def main():

    results = {}

    for name, path in FILES.items():

        if not path.exists():
            raise SystemExit(f"Missing {path}")

        data = load(path)

        results[name] = {
            "file": str(path),
            "keys": list(data.keys())
        }

    countries = load(FILES["countries"])["countries"]

    missing = []

    for country in countries:
        for key in [
            "iso_alpha2",
            "name",
            "calling_codes",
            "timezones"
        ]:
            if key not in country:
                missing.append(
                    f"{country.get('name','unknown')} missing {key}"
                )

    if missing:
        raise SystemExit(
            "\n".join(missing)
        )

    print("Registry validation passed")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
