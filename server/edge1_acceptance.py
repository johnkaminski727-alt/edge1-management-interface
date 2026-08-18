#!/usr/bin/env python3
"""One-command read-only Edge1 acceptance/evidence runner."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from .edge1_snapshot import collect_snapshot
    from .edge1_drift import compare as compare_drift
except ImportError:
    from edge1_snapshot import collect_snapshot
    from edge1_drift import compare as compare_drift

CONTRACT = "wwcx.edge1.acceptance.v1"


def _command_result(value: Any) -> Any:
    if isinstance(value, dict) and value.get("status") == "ok":
        return value.get("result")
    return None


def _test(test_id: str, status: str, evidence: Any, recommendation: str = "") -> dict[str, Any]:
    return {"id": test_id, "status": status, "evidence": evidence, "recommended_next_action": recommendation}


def assess(expected: dict[str, Any], snapshot: dict[str, Any], drift: dict[str, Any]) -> dict[str, Any]:
    tests: list[dict[str, Any]] = []
    contract_ok = snapshot.get("contract") == "wwcx.edge1.snapshot.v1"
    tests.append(_test("edge1.snapshot.contract", "PASS" if contract_ok else "FAIL", snapshot.get("contract"),
                       "Capture a compatible snapshot." if not contract_ok else ""))
    ro_ok = snapshot.get("read_only") is True and snapshot.get("mutation_performed") is False
    tests.append(_test("edge1.snapshot.read_only", "PASS" if ro_ok else "FAIL",
                       {"read_only": snapshot.get("read_only"), "mutation_performed": snapshot.get("mutation_performed")},
                       "Stop acceptance and inspect the collector contract." if not ro_ok else ""))

    ops = _command_result(snapshot.get("services", {}).get("operations_api_health"))
    ops_ok = isinstance(ops, dict) and ops.get("status") == "ok"
    tests.append(_test("edge1.operations_api.health", "PASS" if ops_ok else "BLOCKED",
                       ops, "Verify the loopback Operations API and its authentication/audit boundary." if not ops_ok else ""))

    bigbird = _command_result(snapshot.get("services", {}).get("bigbird_health"))
    bigbird_ok = isinstance(bigbird, dict) and bigbird.get("status") in {"ok", "healthy", "ready"}
    tests.append(_test("bigbird.health", "PASS" if bigbird_ok else "BLOCKED", bigbird,
                       "Inspect BigBird service/runtime health before deployment claims." if not bigbird_ok else ""))

    failed = _command_result(snapshot.get("services", {}).get("failed"))
    if failed is None:
        failed_status = "BLOCKED"
    elif isinstance(failed, str) and not failed.strip():
        failed_status = "PASS"
    else:
        failed_status = "WARN"
    tests.append(_test("edge1.failed_services", failed_status, failed,
                       "Classify each failed service; do not restart unrelated services." if failed_status != "PASS" else ""))

    for item in drift.get("items", []):
        classification = item.get("classification")
        component = item.get("component", "unknown")
        severity = item.get("severity")
        if classification == "MATCH":
            status = "PASS"
        elif classification in {"UNKNOWN", "UNVERIFIABLE"}:
            status = "BLOCKED"
        elif severity == "critical":
            status = "FAIL"
        else:
            status = "WARN"
        tests.append(_test(f"drift.{component}", status, item, item.get("recommended_next_action", "")))

    listener_drift = next((item for item in drift.get("items", []) if item.get("component") == "security.operations_api_listener"), None)
    if listener_drift is None:
        tests.append(_test("security.operations_api_listener", "BLOCKED", None,
                           "Capture listener evidence before claiming the private management boundary."))

    if expected.get("security_boundaries", {}).get("operator_private") is True:
        operator_transport = snapshot.get("operator_transport")
        status = "PASS" if isinstance(operator_transport, dict) and operator_transport.get("private") is True else "BLOCKED"
        tests.append(_test("security.operator_private_transport", status, operator_transport,
                           "Complete and freshly verify the approved private MCP/tunnel attachment." if status != "PASS" else ""))

    if expected.get("security_boundaries", {}).get("generic_exec_disabled") is True:
        generic_exec = snapshot.get("operator_capabilities", {}).get("generic_exec_disabled")
        status = "PASS" if generic_exec is True else "BLOCKED"
        tests.append(_test("security.generic_exec_disabled", status, generic_exec,
                           "Verify the live operator tool registry contains no generic execution capability." if status != "PASS" else ""))

    counts = {name: sum(1 for test in tests if test["status"] == name) for name in ("PASS", "FAIL", "WARN", "BLOCKED")}
    if counts["FAIL"]:
        overall = "FAIL"
    elif counts["WARN"]:
        overall = "WARN"
    elif counts["BLOCKED"]:
        overall = "BLOCKED"
    else:
        overall = "PASS"
    return {
        "schema_version": 1,
        "contract": CONTRACT,
        "collected_at_utc": snapshot.get("collected_at_utc"),
        "read_only": True,
        "mutation_performed": False,
        "result": overall,
        "counts": counts,
        "repository_heads": {
            "expected": expected.get("repositories", {}).get("edge1", {}).get("head"),
            "observed": _command_result(snapshot.get("repository", {}).get("head")),
        },
        "tests": tests,
        "unresolved_blockers": [test for test in tests if test["status"] == "BLOCKED"],
        "failures": [test for test in tests if test["status"] == "FAIL"],
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Edge1 Acceptance and Evidence Report",
        "",
        f"- Contract: `{report['contract']}`",
        f"- Result: **{report['result']}**",
        f"- Collected UTC: `{report.get('collected_at_utc')}`",
        f"- Expected repository head: `{report['repository_heads'].get('expected')}`",
        f"- Observed repository head: `{report['repository_heads'].get('observed')}`",
        "",
        "| Test | Status |",
        "|---|---|",
    ]
    for test in report["tests"]:
        lines.append(f"| `{test['id']}` | **{test['status']}** |")
    if report["unresolved_blockers"]:
        lines.extend(("", "## Unresolved blockers", ""))
        for test in report["unresolved_blockers"]:
            lines.append(f"- `{test['id']}` — {test.get('recommended_next_action') or 'Additional evidence required.'}")
    if report["failures"]:
        lines.extend(("", "## Failures", ""))
        for test in report["failures"]:
            lines.append(f"- `{test['id']}` — {test.get('recommended_next_action') or 'Investigate before proceeding.'}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("expected", type=Path)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()
    expected = json.loads(args.expected.read_text(encoding="utf-8"))
    snapshot = collect_snapshot()
    drift = compare_drift(expected, snapshot)
    report = assess(expected, snapshot, drift)
    if args.format == "markdown":
        print(render_markdown(report), end="")
    else:
        print(json.dumps(report, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
