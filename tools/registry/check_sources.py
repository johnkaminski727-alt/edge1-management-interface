#!/usr/bin/env python3

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

manifest = ROOT / "data/registry/sources/manifest.json"

if not manifest.exists():
    raise SystemExit("Missing registry source manifest")

data = json.loads(manifest.read_text())

print("Registry sources:")

for name, source in data["sources"].items():
    print(
        f"- {name}: "
        f"{source['standard']} "
        f"({source['status']})"
    )
