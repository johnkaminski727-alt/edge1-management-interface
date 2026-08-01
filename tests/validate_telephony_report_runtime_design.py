#!/usr/bin/env python3
"""Validate the disabled telephony aggregate-report runtime design."""
from __future__ import annotations

import ast
import copy
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from telephony_report_runtime_policy import (  # noqa: E402
    RuntimePolicyError,
    canonical_json,
    normalize_runtime_policy,
    runtime_plan,
)

POLICY = ROOT / "config" / "telephony" / "analytics-report-runtime-policy.json"
SCHEMA = ROOT / "schemas" / "telephony" / "analytics-report-runtime-policy.schema.json"
PLAN_EXAMPLE = ROOT / "examples" / "telephony" / "analytics-report-runtime-plan.example.json"
MODULE = ROOT / "server" / "telephony_report_runtime_policy.py"
CLI = ROOT / "tools" / "telephony" / "plan_telephony_report_runtime.py"
SERVICE = ROOT / "design" / "telephony" / "systemd" / "wwcx-telephony-aggregate-report.service"
TIMER = ROOT / "design" / "telephony" / "systemd" / "wwcx-telephony-aggregate-report.timer"
DOC = ROOT / "docs" / "telephony" / "aggregate-report-runtime-design.md"
ACCEPTANCE = ROOT / "docs" / "telephony" / "aggregate-report-runtime-design-repository-acceptance-20260801.md"
RUNNER = ROOT / "tools" / "telephony" / "run_telephony_aggregate_report.py"

for path in (POLICY, SCHEMA, PLAN_EXAMPLE, MODULE, CLI, SERVICE, TIMER, DOC, ACCEPTANCE):
    if not path.is_file():
        raise SystemExit(f"missing runtime design asset: {path.relative_to(ROOT)}")
assert not RUNNER.exists(), "design-only runtime must not include an executable runner"

module_source = MODULE.read_text(encoding="utf-8")
cli_source = CLI.read_text(encoding="utf-8")
ast.parse(module_source, filename=str(MODULE))
ast.parse(cli_source, filename=str(CLI))

for marker in (
    "design_only",
    "blocked_pending_separate_authorization_and_runner",
    "mutations_performed",
    "activation_sentinel_not_created_by_design",
    "retain_until_separately_authorized_checkpoint",
):
    if marker not in module_source:
        raise SystemExit(f"runtime policy module missing marker: {marker}")

for forbidden in (
    "os.mkdir",
    "Path.mkdir",
    "write_text",
    "write_bytes",
    "unlink(",
    "rmdir(",
    "import socket",
    "import subprocess",
    "import sqlite3",
    "import urllib",
    "import requests",
    "systemctl",
    "crontab",
    "append_audit_event",
):
    if forbidden in module_source or forbidden in cli_source:
        raise SystemExit(f"runtime planner contains prohibited mutation path: {forbidden}")

policy = json.loads(POLICY.read_text(encoding="utf-8"))
schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
expected_plan = json.loads(PLAN_EXAMPLE.read_text(encoding="utf-8"))
normalized = normalize_runtime_policy(policy)
plan = runtime_plan(normalized)
assert plan == expected_plan
assert plan["status"] == "blocked_pending_separate_authorization_and_runner"
assert plan["mutations_performed"] is False
assert schema["additionalProperties"] is False
assert schema["properties"]["enabled"]["const"] is False
assert schema["properties"]["deployment_authorized"]["const"] is False
assert schema["properties"]["execution"]["properties"]["runner_implemented"]["const"] is False
for value in schema["properties"]["safety"]["properties"].values():
    assert value["const"] is False


def rejected(value: dict[str, object], expected: str) -> None:
    try:
        normalize_runtime_policy(value)
    except RuntimePolicyError as exc:
        if expected not in str(exc):
            raise AssertionError(f"unexpected policy rejection: {exc}") from exc
    else:
        raise AssertionError("unsafe runtime policy was accepted")


for path in (("enabled",), ("deployment_authorized",)):
    unsafe = copy.deepcopy(policy)
    unsafe[path[0]] = True
    rejected(unsafe, "must remain false")

unsafe = copy.deepcopy(policy)
unsafe["execution"]["runner_implemented"] = True
rejected(unsafe, "must remain false")

unsafe = copy.deepcopy(policy)
unsafe["scheduler"]["enabled"] = True
rejected(unsafe, "must remain false")

unsafe = copy.deepcopy(policy)
unsafe["audit"]["append_enabled"] = True
rejected(unsafe, "must remain false")

unsafe = copy.deepcopy(policy)
unsafe["retention"]["enabled"] = True
rejected(unsafe, "must remain false")

unsafe = copy.deepcopy(policy)
unsafe["safety"]["host_mutation"] = True
rejected(unsafe, "must remain false")

unsafe = copy.deepcopy(policy)
unsafe["paths"]["runtime_root"] = "/tmp/reports"
rejected(unsafe, "protected root")

unsafe = copy.deepcopy(policy)
unsafe["paths"]["audit_log"] = "/var/tmp/report-events.jsonl"
rejected(unsafe, "must remain below")

unsafe = copy.deepcopy(policy)
unsafe["permissions"]["file_mode"] = "0640"
rejected(unsafe, "owner-only")

spec = importlib.util.spec_from_file_location("telephony_runtime_planner", CLI)
assert spec is not None and spec.loader is not None
planner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(planner)
assert planner.read_policy(POLICY) == policy

with tempfile.TemporaryDirectory() as temp_dir:
    root = Path(temp_dir)
    policy_copy = root / "policy.json"
    policy_copy.write_text(json.dumps(policy), encoding="utf-8")
    policy_link = root / "policy-link.json"
    policy_link.symlink_to(policy_copy)
    try:
        planner.read_policy(policy_link)
    except RuntimePolicyError as exc:
        assert "symlink" in str(exc)
    else:
        raise AssertionError("symlink policy was accepted")

try:
    planner.read_policy(Path("relative-policy.json"))
except RuntimePolicyError as exc:
    assert "absolute" in str(exc)
else:
    raise AssertionError("relative policy was accepted")

service = SERVICE.read_text(encoding="utf-8")
timer = TIMER.read_text(encoding="utf-8")
for text in (service, timer):
    assert "ConditionPathExists=/etc/wwcx-telephony/analytics-report-runtime-enabled" in text
    assert "ConditionFileIsExecutable=/opt/edge1-management-interface/tools/telephony/run_telephony_aggregate_report.py" in text
    assert "[Install]" not in text
assert "RestrictAddressFamilies=AF_UNIX" in service
assert "User=wwadmin" in service and "Group=wwadmin" in service
assert "UMask=0077" in service
assert "ReadWritePaths=/var/lib/wwcx-telephony-analytics-reports /var/lib/wwcx-deployment-evidence/telephony-analytics-report-runtime" in service
assert "OnCalendar=*-*-* 02:15:00 UTC" in timer
assert "RandomizedDelaySec=15m" in timer
assert "Persistent=false" in timer

for path in (DOC, ACCEPTANCE):
    text = path.read_text(encoding="utf-8")
    for marker in (
        "Design-only policy",
        "Missing activation sentinel",
        "Audit append gate",
        "Retention design",
        "No runtime activation",
    ):
        if marker not in text:
            raise SystemExit(f"{path.name} missing marker: {marker}")

assert canonical_json(plan) + "\n" == PLAN_EXAMPLE.read_text(encoding="utf-8")
print("telephony report runtime design validation passed")
