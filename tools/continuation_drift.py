#!/usr/bin/env python3
"""Read-only comparison of repository-expected state with a live Edge1 snapshot."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

VALID = {"MATCH", "DRIFT", "UNKNOWN", "NOT DEPLOYED", "LIVE NEWER THAN REPOSITORY"}


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def classify_scalar(expected: Any, live: Any) -> str:
    if live is None or live == "":
        return "UNKNOWN"
    if isinstance(live, dict) and live.get("status") == "not-deployed":
        return "NOT DEPLOYED"
    if expected is None or expected == "":
        return "UNKNOWN"
    return "MATCH" if expected == live else "DRIFT"


def classify_git(expected: str | None, live: str | None, repo: Path | None) -> str:
    base = classify_scalar(expected, live)
    if base != "DRIFT" or repo is None or not expected or not live:
        return base
    try:
        result = subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", expected, live], check=False, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return "DRIFT"
    if result.returncode == 0:
        return "LIVE NEWER THAN REPOSITORY"
    return "DRIFT"


def compare(expected: dict[str, Any], live: dict[str, Any], repo: Path | None = None) -> dict[str, Any]:
    expected_edge1 = expected.get("repository_heads", {}).get("edge1-management-interface", {}).get("expected_head")
    live_edge1 = live.get("edge1_checkout_head")
    checks = {
        "edge1_checkout_head": {"expected": expected_edge1, "live": live_edge1, "classification": classify_git(expected_edge1, live_edge1, repo)},
        "bigbird_version": {"expected": expected.get("live_state", {}).get("bigbird_version"), "live": live.get("bigbird_version"), "classification": classify_scalar(expected.get("live_state", {}).get("bigbird_version"), live.get("bigbird_version"))},
        "operator_service": {"expected": expected.get("live_state", {}).get("operator_service"), "live": live.get("operator_service"), "classification": classify_scalar(expected.get("live_state", {}).get("operator_service"), live.get("operator_service"))},
        "operations_api_service": {"expected": expected.get("live_state", {}).get("operations_api_service"), "live": live.get("operations_api_service"), "classification": classify_scalar(expected.get("live_state", {}).get("operations_api_service"), live.get("operations_api_service"))}
    }
    classifications = {item["classification"] for item in checks.values()}
    if "DRIFT" in classifications:
        overall = "DRIFT"
    elif "LIVE NEWER THAN REPOSITORY" in classifications:
        overall = "LIVE NEWER THAN REPOSITORY"
    elif "NOT DEPLOYED" in classifications:
        overall = "NOT DEPLOYED"
    elif classifications == {"MATCH"}:
        overall = "MATCH"
    else:
        overall = "UNKNOWN"
    assert overall in VALID
    return {"schema": "wwcx-edge1-drift-report-v1", "overall": overall, "checks": checks}


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare expected and sanitized live Edge1 state")
    parser.add_argument("expected", type=Path)
    parser.add_argument("live", type=Path)
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = compare(read_json(args.expected), read_json(args.live), args.repo)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
