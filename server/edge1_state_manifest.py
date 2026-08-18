#!/usr/bin/env python3
"""Generate a sanitized machine-readable Edge1 continuation/current-state manifest."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
from pathlib import Path
from typing import Any

CONTRACT = "wwcx.edge1.current-state.v1"
REPO_ROOT = Path(__file__).resolve().parents[1]


def _git(*args: str) -> str | None:
    try:
        cp = subprocess.run(["git", "-C", str(REPO_ROOT), *args], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            check=False, timeout=15, text=True)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return cp.stdout.strip() if cp.returncode == 0 else None


def build_manifest(*, expected: dict[str, Any] | None = None, snapshot: dict[str, Any] | None = None,
                   drift: dict[str, Any] | None = None, acceptance: dict[str, Any] | None = None,
                   library: dict[str, Any] | None = None) -> dict[str, Any]:
    expected = expected or {}
    live_verified = snapshot is not None and snapshot.get("contract") == "wwcx.edge1.snapshot.v1"
    observed_head = None
    if snapshot:
        head = snapshot.get("repository", {}).get("head", {})
        if isinstance(head, dict) and head.get("status") == "ok":
            observed_head = head.get("result")
    expected_head = expected.get("repositories", {}).get("edge1", {}).get("head") or _git("rev-parse", "HEAD")
    branch = expected.get("repositories", {}).get("edge1", {}).get("branch") or _git("branch", "--show-current")
    drift_result = (drift or {}).get("summary", {}).get("result")
    acceptance_result = (acceptance or {}).get("result")
    blockers = []
    if not live_verified:
        blockers.append({"id": "fresh-live-edge1-snapshot", "status": "BLOCKED", "owner": "human/live-access-boundary",
                         "next_action": "Obtain authenticated Edge1 execution and collect edge1.snapshot."})
    if acceptance:
        for row in acceptance.get("unresolved_blockers", []):
            blockers.append({"id": row.get("id"), "status": "BLOCKED", "owner": "evidence/runtime",
                             "next_action": row.get("recommended_next_action")})
    return {
        "schema_version": 1,
        "contract": CONTRACT,
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "evidence_classification": "LIVE-VERIFIED" if live_verified else "REPOSITORY-CONFIRMED / BLOCKED-UNVERIFIED-LIVE",
        "repositories": {
            "edge1": {"head": expected_head, "branch": branch, "clean_expected_state": True},
            "wwcx": expected.get("repositories", {}).get("wwcx", {"head": None, "branch": "main"}),
        },
        "live": {
            "last_verified_at": snapshot.get("collected_at_utc") if snapshot else None,
            "edge1_hostname": snapshot.get("identity", {}).get("hostname") if snapshot else None,
            "edge1_version_or_build": observed_head,
            "bigbird_version": (snapshot or {}).get("bigbird_version"),
            "operator_version": (snapshot or {}).get("operator_version"),
            "operations_api_version": (snapshot or {}).get("operations_api_version"),
            "apache_state": (snapshot or {}).get("apache_state"),
            "asterisk_state": (snapshot or {}).get("asterisk_state"),
        },
        "deployment": {
            "expected_version": expected_head,
            "observed_version": observed_head,
            "drift_status": drift_result,
        },
        "acceptance": {
            "last_run": acceptance.get("collected_at_utc") if acceptance else None,
            "result": acceptance_result,
            "report_location": None,
        },
        "security_boundaries": {
            "operator_private": expected.get("security_boundaries", {}).get("operator_private"),
            "generic_exec_disabled": expected.get("security_boundaries", {}).get("generic_exec_disabled"),
            "auth_verified": (snapshot or {}).get("operator_security", {}).get("auth_verified"),
            "replay_protection_verified": (snapshot or {}).get("operator_security", {}).get("replay_protection_verified"),
            "audit_verified": (snapshot or {}).get("operator_security", {}).get("audit_verified"),
        },
        "library": library or {"cleanup_register": None, "canonical_bigbird_records": [], "unresolved_artifacts": []},
        "blockers": blockers,
        "outstanding_milestones": expected.get("outstanding_milestones", []),
        "next_safe_actions": expected.get("next_safe_actions", []),
        "rollback_points": expected.get("rollback_points", []),
        "unresolved_drift": [row for row in (drift or {}).get("items", []) if row.get("classification") != "MATCH"],
        "secrets_present": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected", type=Path)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--drift", type=Path)
    parser.add_argument("--acceptance", type=Path)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8")) if path else None
    print(json.dumps(build_manifest(expected=load(args.expected), snapshot=load(args.snapshot),
                                    drift=load(args.drift), acceptance=load(args.acceptance)),
                     sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
