#!/usr/bin/env python3
"""Auditable PLAN/BACKUP/VALIDATE/APPLY/VERIFY/ROLLBACK orchestration.

Only operations committed to the repository-controlled registry can run. The
CLI never accepts command strings or argv. The initial registry is deliberately
empty until a concrete reversible production operation is separately reviewed.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config" / "safe-change-operations.json"
PHASES = ("PLAN", "BACKUP", "VALIDATE", "APPLY", "VERIFY", "ROLLBACK")
FORWARD_PHASES = PHASES[:5]


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_registry(path: Path = REGISTRY) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != 1 or not isinstance(data.get("operations"), dict):
        raise ValueError("unsupported safe-change registry")
    for name, operation in data["operations"].items():
        if not isinstance(name, str) or not name or not isinstance(operation, dict):
            raise ValueError("invalid operation entry")
        phase_map = operation.get("phases")
        if not isinstance(phase_map, dict) or set(phase_map) != set(PHASES):
            raise ValueError(f"operation {name} must define exactly {', '.join(PHASES)}")
        for phase in PHASES:
            spec = phase_map[phase]
            if not isinstance(spec, dict):
                raise ValueError(f"operation {name} phase {phase} must be an object")
            argv = spec.get("argv")
            if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x for x in argv):
                raise ValueError(f"operation {name} phase {phase} must use fixed argv")
            if spec.get("timeout_seconds", 0) <= 0:
                raise ValueError(f"operation {name} phase {phase} needs a positive timeout")
    return data


def public_plan(name: str, operation: dict[str, Any]) -> dict[str, Any]:
    return {
        "operation": name,
        "description": operation.get("description", ""),
        "automatic_rollback_on_verify_failure": bool(operation.get("automatic_rollback_on_verify_failure", False)),
        "phases": [{"phase": phase, "argv_id": operation["phases"][phase].get("argv_id", phase.lower())} for phase in PHASES],
    }


def run_phase(name: str, phase: str, spec: dict[str, Any]) -> dict[str, Any]:
    started = utcnow()
    try:
        result = subprocess.run(
            spec["argv"], cwd=str(ROOT), capture_output=True, text=True,
            timeout=int(spec["timeout_seconds"]), check=False,
            env={"PATH": os.environ.get("PATH", "/usr/sbin:/usr/bin:/sbin:/bin"), "LANG": "C", "LC_ALL": "C"},
        )
        return {
            "operation": name, "phase": phase, "argv_id": spec.get("argv_id", phase.lower()),
            "started_utc": started, "exit_code": result.returncode,
            "status": "pass" if result.returncode == 0 else "fail",
            "stdout": result.stdout.replace("\x00", "")[-20000:],
            "stderr": result.stderr.replace("\x00", "")[-20000:],
        }
    except subprocess.TimeoutExpired:
        return {"operation": name, "phase": phase, "argv_id": spec.get("argv_id", phase.lower()), "started_utc": started, "exit_code": None, "status": "timeout", "stdout": "", "stderr": "phase timed out"}
    except OSError as exc:
        return {"operation": name, "phase": phase, "argv_id": spec.get("argv_id", phase.lower()), "started_utc": started, "exit_code": None, "status": "unavailable", "stdout": "", "stderr": str(exc)[-2000:]}


def execute(name: str, operation: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for phase in FORWARD_PHASES:
        result = run_phase(name, phase, operation["phases"][phase])
        results.append(result)
        if result["status"] != "pass":
            if phase == "VERIFY" and operation.get("automatic_rollback_on_verify_failure") is True:
                results.append(run_phase(name, "ROLLBACK", operation["phases"]["ROLLBACK"]))
            break
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a repository-registered safe change workflow")
    parser.add_argument("operation", nargs="?")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--execute", action="store_true", help="execute registered forward phases; otherwise print plan only")
    parser.add_argument("--rollback", action="store_true", help="run only the registered rollback phase")
    parser.add_argument("--registry", type=Path, default=REGISTRY, help=argparse.SUPPRESS)
    args = parser.parse_args()
    registry = load_registry(args.registry)
    operations = registry["operations"]
    if args.list:
        print(json.dumps({"operations": sorted(operations)}, sort_keys=True))
        return 0
    if not args.operation or args.operation not in operations:
        raise SystemExit("unknown or missing registered operation")
    operation = operations[args.operation]
    if not args.execute and not args.rollback:
        print(json.dumps(public_plan(args.operation, operation), indent=2, sort_keys=True))
        return 0
    if args.execute and args.rollback:
        raise SystemExit("choose --execute or --rollback, not both")
    if args.rollback:
        results = [run_phase(args.operation, "ROLLBACK", operation["phases"]["ROLLBACK"])]
    else:
        results = execute(args.operation, operation)
    print(json.dumps({"schema": "wwcx-safe-change-evidence-v1", "generated_utc": utcnow(), "results": results}, indent=2, sort_keys=True))
    return 0 if results and all(item["status"] == "pass" for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
