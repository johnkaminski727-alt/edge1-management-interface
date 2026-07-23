#!/usr/bin/env python3
"""
WW.CX Registry Refresh Coordinator

Tracks registry refresh operations and rebuilds derived data.
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[2]

REGISTRY = ROOT / "data" / "registry"
MANIFEST = REGISTRY / "registry-manifest.json"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def collect():

    datasets = {}

    for path in REGISTRY.glob("*.json"):

        if path.name == "registry-manifest.json":
            continue

        datasets[path.name] = {
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
            "updated": datetime.fromtimestamp(
                path.stat().st_mtime,
                timezone.utc
            ).isoformat()
        }

    return datasets


def main():

    manifest = {
        "schema_version": "1.0",
        "generated_at": utc_now(),
        "datasets": collect()
    }

    MANIFEST.write_text(
        json.dumps(
            manifest,
            indent=2
        )
    )

    print("Registry refresh manifest generated")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
