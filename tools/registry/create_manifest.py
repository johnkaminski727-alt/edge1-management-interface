#!/usr/bin/env python3

import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]

FILES = [
    "calling_codes.json",
    "countries.json",
    "timezones.json",
]


def sha256(path):
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


manifest = {
    "schema_version": "1.0",
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "datasets": {}
}

for f in FILES:
    p = ROOT / "data/registry" / f

    manifest["datasets"][f] = {
        "sha256": sha256(p),
        "bytes": p.stat().st_size
    }


(ROOT / "data/registry/registry-manifest.json").write_text(
    json.dumps(manifest, indent=2)
)

print("Created registry manifest")
