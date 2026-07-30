#!/usr/bin/env python3
"""Reconcile a supplied read-only Edge1 filesystem inventory against the merged manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))

from edge1_ops_access_policy import load_policy as load_access_policy  # noqa: E402
from edge1_restricted_artifact_manifest import (  # noqa: E402
    load_object,
    reconcile_inventory,
)

DEFAULT_MANIFEST = ROOT / "config/security/edge1-restricted-artifact-migration-manifest.json"
DEFAULT_ACCESS_POLICY = ROOT / "config/security/edge1-authenticated-operations-policy.json"


def load_inventory(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError("inventory JSON must be an array")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--access-policy", type=Path, default=DEFAULT_ACCESS_POLICY)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    inventory = load_inventory(args.inventory)
    manifest = load_object(args.manifest)
    access_policy = load_access_policy(args.access_policy)
    result = reconcile_inventory(manifest, access_policy, inventory)
    result.update({
        "inventory_sha256": sha256(args.inventory),
        "inventory_path_recorded": args.inventory.name,
        "live_files_opened_by_reconciler": False,
        "source_tree_mutated": False,
        "credentials_collected": False,
    })
    if args.output:
        atomic_write(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
