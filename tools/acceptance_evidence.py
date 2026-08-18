#!/usr/bin/env python3
"""Deterministic acceptance/evidence runner for WW.CX Edge1.

Only fixed repository-owned checks are available. No arbitrary command input is
accepted. Source checks are the default; optional live checks remain read-only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

SOURCE_CHECKS = (
    ("python_compile", ("python3", "-m", "compileall", "-q", "server", "tools"), 120),
    ("operator_tests", ("python3", "-m", "pytest", "-q", "tests/test_edge1_operator_bounded_tools.py", "tests/test_edge1_operator_integration_flow.py"), 300),
    ("continuation_tests", ("python3", "-m", "pytest", "-q", "tests/test_continuation_accelerators.py"), 120),
    ("operations_allowlist_json", ("python3", "-m", "json.tool", "config/edge1-operations-allowlist.json"), 30),
    ("continuation_manifest_json", ("python3", "-m", "json.tool", "config/continuation-manifest.json"), 30),
)

LIVE_READ_ONLY_CHECKS = (
    ("edge1_snapshot", ("python3", "server/edge1_snapshot.py"), 180),
)


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def safe_text(value: str, limit: int = 20000) -> str:
    return value.replace("\x00", "")[-limit:]


def run_check(name: str, argv: tuple[str, ...], timeout: int, root: Path = ROOT) -> dict[str, Any]:
    started = utcnow()
    try:
        result = subprocess.run(
            list(argv), cwd=str(root), capture_output=True, text=True,
            timeout=timeout, check=False,
            env={"PATH": os.environ.get("PATH", "/usr/sbin:/usr/bin:/sbin:/bin"), "LANG": "C", "LC_ALL": "C"},
        )
        return {
            "name": name,
            "started_utc": started,
            "argv_id": name,
            "exit_code": result.returncode,
            "status": "pass" if result.returncode == 0 else "fail",
            "stdout": safe_text(result.stdout),
            "stderr": safe_text(result.stderr),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "started_utc": started,
            "argv_id": name,
            "exit_code": None,
            "status": "timeout",
            "stdout": safe_text(exc.stdout or ""),
            "stderr": safe_text(exc.stderr or ""),
        }
    except OSError as exc:
        return {
            "name": name,
            "started_utc": started,
            "argv_id": name,
            "exit_code": None,
            "status": "unavailable",
            "stdout": "",
            "stderr": safe_text(str(exc)),
        }


def write_evidence(output_root: Path, results: list[dict[str, Any]], live_read_only: bool) -> Path:
    directory = output_root / stamp()
    directory.mkdir(parents=True, exist_ok=False)
    summary = {
        "schema": "wwcx-edge1-acceptance-evidence-v1",
        "generated_utc": utcnow(),
        "live_read_only_enabled": live_read_only,
        "overall": "pass" if all(item["status"] == "pass" for item in results) else "attention",
        "results": [{k: v for k, v in item.items() if k not in {"stdout", "stderr"}} for item in results],
    }
    for item in results:
        (directory / f"{item['name']}.json").write_text(json.dumps(item, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (directory / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hashes = []
    for path in sorted(directory.glob("*.json")):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        hashes.append(f"{digest}  {path.name}")
    (directory / "SHA256SUMS").write_text("\n".join(hashes) + "\n", encoding="utf-8")
    return directory


def main() -> int:
    parser = argparse.ArgumentParser(description="Run fixed Edge1 acceptance checks and retain hashed evidence")
    parser.add_argument("--output-root", type=Path, default=Path(".edge1-acceptance-evidence"))
    parser.add_argument("--live-read-only", action="store_true", help="also run the deterministic read-only Edge1 snapshot")
    args = parser.parse_args()
    checks = list(SOURCE_CHECKS)
    if args.live_read_only:
        checks.extend(LIVE_READ_ONLY_CHECKS)
    results = [run_check(name, argv, timeout) for name, argv, timeout in checks]
    directory = write_evidence(args.output_root, results, args.live_read_only)
    print(json.dumps({"evidence_dir": str(directory), "overall": "pass" if all(r["status"] == "pass" for r in results) else "attention"}, sort_keys=True))
    return 0 if all(item["status"] == "pass" for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
