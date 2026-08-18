#!/usr/bin/env python3
"""Generate a sanitized WW.CX / Edge1 continuation snapshot.

The committed manifest uses ``SELF`` for the Edge1 repository head so the file
can describe the commit that contains it without embedding a forever-stale
self-referential SHA. This generator resolves SELF from the current checkout.
"""
from __future__ import annotations

import argparse
import copy
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "config" / "continuation-manifest.json"


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def git_head(root: Path = ROOT) -> str:
    result = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True, text=True, timeout=10)
    value = result.stdout.strip()
    if len(value) != 40 or any(ch not in "0123456789abcdef" for ch in value.lower()):
        raise ValueError("git HEAD is not a 40-character hexadecimal commit id")
    return value.lower()


def load_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != "wwcx-edge1-continuation-v1":
        raise ValueError("unsupported continuation manifest schema")
    heads = data.get("repository_heads")
    if not isinstance(heads, dict) or "edge1-management-interface" not in heads:
        raise ValueError("manifest is missing the Edge1 repository head declaration")
    return data


def build_snapshot(manifest: dict[str, Any], head: str) -> dict[str, Any]:
    snapshot = copy.deepcopy(manifest)
    edge1 = snapshot["repository_heads"]["edge1-management-interface"]
    if edge1.get("expected_head") == "SELF":
        edge1["expected_head"] = head
        edge1["resolved_from"] = "SELF"
    snapshot["generated_utc"] = utcnow()
    snapshot["generator"] = "tools/continuation_manifest.py"
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate sanitized Edge1 continuation JSON")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    snapshot = build_snapshot(load_manifest(args.manifest), git_head(ROOT))
    rendered = json.dumps(snapshot, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
