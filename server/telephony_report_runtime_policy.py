#!/usr/bin/env python3
"""Validate and render the disabled telephony report runtime design.

This module is intentionally non-mutating. It validates one fixed design-only
policy and renders a deterministic plan. It does not inspect or change the host,
create paths, install units, enable timers, append audit events, or prune files.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = "1.0"
MODE = "design_only"
EXPECTED_OWNER = "wwadmin"
EXPECTED_GROUP = "wwadmin"
EXPECTED_RUNTIME_ROOT = Path("/var/lib/wwcx-telephony-analytics-reports")
EXPECTED_EVIDENCE_ROOT = Path("/var/lib/wwcx-deployment-evidence/telephony-analytics-report-runtime")
EXPECTED_SENTINEL = Path("/etc/wwcx-telephony/analytics-report-runtime-enabled")
EXPECTED_COMMAND = [
    "/usr/bin/python3",
    "/opt/edge1-management-interface/tools/telephony/generate_telephony_analytics_report.py",
    "--input",
    "{incoming_file}",
    "--output-dir",
    "{new_output_dir}",
]
MAX_POLICY_BYTES = 65536

TOP_FIELDS = {
    "schema_version", "mode", "enabled", "deployment_authorized", "owner", "group",
    "paths", "permissions", "input", "output", "audit", "retention", "scheduler",
    "execution", "safety",
}
PATH_FIELDS = {
    "runtime_root", "incoming_dir", "incoming_file", "reports_dir", "audit_dir",
    "audit_log", "activation_sentinel", "evidence_root",
}
PERMISSION_FIELDS = {"runtime_root_mode", "directory_mode", "file_mode", "umask"}
INPUT_FIELDS = {"source_contract", "filename", "max_bytes", "live_collection_enabled"}
OUTPUT_FIELDS = {"bundle_prefix", "no_overwrite", "sha256_manifest", "audit_event_candidate"}
AUDIT_FIELDS = {
    "append_enabled", "automatic_append", "chain_verification_required", "prune_events",
    "retention_policy",
}
RETENTION_FIELDS = {
    "enabled", "dry_run_required", "input_days", "report_days", "minimum_free_bytes",
    "delete_unmanifested",
}
SCHEDULER_FIELDS = {
    "enabled", "timezone", "on_calendar", "randomized_delay_seconds", "persistent",
}
EXECUTION_FIELDS = {
    "runner_implemented", "service_name", "timer_name", "command_template", "network_access",
}
SAFETY_FIELDS = {
    "host_mutation", "service_install", "service_enable", "service_start", "timer_enable",
    "live_source_access", "audit_log_append", "retention_delete", "notification_dispatch",
    "traffic_enforcement", "route_change", "call_origination", "dtmf_transmission",
}
SAFE_NAME_RE = re.compile(r"^[a-z][a-z0-9._-]{0,95}$")


class RuntimePolicyError(ValueError):
    """Raised when the design-only runtime policy violates its fixed boundary."""


def canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _exact(value: Any, fields: set[str], name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RuntimePolicyError(f"{name} must be a mapping")
    if set(value) != fields:
        missing = sorted(fields - set(value))
        extra = sorted(set(value) - fields)
        raise RuntimePolicyError(f"{name} fields do not match contract; missing={missing} extra={extra}")
    return value


def _false(value: Any, name: str) -> bool:
    if value is not False:
        raise RuntimePolicyError(f"{name} must remain false in design-only mode")
    return False


def _true(value: Any, name: str) -> bool:
    if value is not True:
        raise RuntimePolicyError(f"{name} must remain true")
    return True


def _positive_int(value: Any, name: str, minimum: int = 1, maximum: int = 10**12) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise RuntimePolicyError(f"{name} is outside the accepted range")
    return value


def _absolute_path(value: Any, name: str) -> Path:
    path = Path(str(value))
    if not path.is_absolute() or ".." in path.parts:
        raise RuntimePolicyError(f"{name} must be an absolute normalized path")
    return path


def _require_child(path: Path, root: Path, name: str) -> None:
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise RuntimePolicyError(f"{name} must remain below {root}") from exc


def normalize_runtime_policy(policy: Mapping[str, Any]) -> dict[str, Any]:
    value = _exact(policy, TOP_FIELDS, "policy")
    if value["schema_version"] != SCHEMA_VERSION:
        raise RuntimePolicyError("unsupported schema_version")
    if value["mode"] != MODE:
        raise RuntimePolicyError("mode must remain design_only")
    _false(value["enabled"], "enabled")
    _false(value["deployment_authorized"], "deployment_authorized")
    if value["owner"] != EXPECTED_OWNER or value["group"] != EXPECTED_GROUP:
        raise RuntimePolicyError("owner and group must remain wwadmin")

    paths = _exact(value["paths"], PATH_FIELDS, "paths")
    normalized_paths = {key: _absolute_path(paths[key], f"paths.{key}") for key in PATH_FIELDS}
    if normalized_paths["runtime_root"] != EXPECTED_RUNTIME_ROOT:
        raise RuntimePolicyError("runtime_root does not match the accepted protected root")
    if normalized_paths["evidence_root"] != EXPECTED_EVIDENCE_ROOT:
        raise RuntimePolicyError("evidence_root does not match the accepted evidence root")
    if normalized_paths["activation_sentinel"] != EXPECTED_SENTINEL:
        raise RuntimePolicyError("activation_sentinel does not match the accepted gate")
    for key in ("incoming_dir", "incoming_file", "reports_dir", "audit_dir", "audit_log"):
        _require_child(normalized_paths[key], EXPECTED_RUNTIME_ROOT, f"paths.{key}")
    if normalized_paths["incoming_file"].parent != normalized_paths["incoming_dir"]:
        raise RuntimePolicyError("incoming_file must remain directly below incoming_dir")
    if normalized_paths["audit_log"].parent != normalized_paths["audit_dir"]:
        raise RuntimePolicyError("audit_log must remain directly below audit_dir")

    permissions = _exact(value["permissions"], PERMISSION_FIELDS, "permissions")
    expected_permissions = {
        "runtime_root_mode": "0700", "directory_mode": "0700",
        "file_mode": "0600", "umask": "0077",
    }
    if dict(permissions) != expected_permissions:
        raise RuntimePolicyError("permissions must remain owner-only")

    input_policy = _exact(value["input"], INPUT_FIELDS, "input")
    if input_policy["source_contract"] != "already_aggregated_summaries_only":
        raise RuntimePolicyError("input source contract is unsupported")
    if input_policy["filename"] != "current.json":
        raise RuntimePolicyError("input filename must remain current.json")
    if input_policy["max_bytes"] != 2097152:
        raise RuntimePolicyError("input max_bytes must match the report generator")
    _false(input_policy["live_collection_enabled"], "input.live_collection_enabled")

    output = _exact(value["output"], OUTPUT_FIELDS, "output")
    if output["bundle_prefix"] != "report-" or not SAFE_NAME_RE.fullmatch(output["bundle_prefix"] + "x"):
        raise RuntimePolicyError("output bundle prefix is unsupported")
    _true(output["no_overwrite"], "output.no_overwrite")
    _true(output["sha256_manifest"], "output.sha256_manifest")
    _true(output["audit_event_candidate"], "output.audit_event_candidate")

    audit = _exact(value["audit"], AUDIT_FIELDS, "audit")
    _false(audit["append_enabled"], "audit.append_enabled")
    _false(audit["automatic_append"], "audit.automatic_append")
    _true(audit["chain_verification_required"], "audit.chain_verification_required")
    _false(audit["prune_events"], "audit.prune_events")
    if audit["retention_policy"] != "retain_until_separately_authorized_checkpoint":
        raise RuntimePolicyError("audit retention policy is unsupported")

    retention = _exact(value["retention"], RETENTION_FIELDS, "retention")
    _false(retention["enabled"], "retention.enabled")
    _true(retention["dry_run_required"], "retention.dry_run_required")
    _positive_int(retention["input_days"], "retention.input_days", 1, 30)
    _positive_int(retention["report_days"], "retention.report_days", 30, 3650)
    _positive_int(retention["minimum_free_bytes"], "retention.minimum_free_bytes", 1048576)
    _false(retention["delete_unmanifested"], "retention.delete_unmanifested")

    scheduler = _exact(value["scheduler"], SCHEDULER_FIELDS, "scheduler")
    _false(scheduler["enabled"], "scheduler.enabled")
    if scheduler["timezone"] != "UTC" or scheduler["on_calendar"] != "*-*-* 02:15:00":
        raise RuntimePolicyError("scheduler must remain the reviewed UTC design")
    _positive_int(scheduler["randomized_delay_seconds"], "scheduler.randomized_delay_seconds", 0, 3600)
    _false(scheduler["persistent"], "scheduler.persistent")

    execution = _exact(value["execution"], EXECUTION_FIELDS, "execution")
    _false(execution["runner_implemented"], "execution.runner_implemented")
    if execution["service_name"] != "wwcx-telephony-aggregate-report.service":
        raise RuntimePolicyError("service_name is unsupported")
    if execution["timer_name"] != "wwcx-telephony-aggregate-report.timer":
        raise RuntimePolicyError("timer_name is unsupported")
    if execution["command_template"] != EXPECTED_COMMAND:
        raise RuntimePolicyError("command_template does not match the reviewed generator invocation")
    _false(execution["network_access"], "execution.network_access")

    safety = _exact(value["safety"], SAFETY_FIELDS, "safety")
    for key in sorted(SAFETY_FIELDS):
        _false(safety[key], f"safety.{key}")

    return json.loads(json.dumps(value, sort_keys=True, separators=(",", ":")))


def runtime_plan(policy: Mapping[str, Any]) -> dict[str, Any]:
    value = normalize_runtime_policy(policy)
    paths = value["paths"]
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": MODE,
        "status": "blocked_pending_separate_authorization_and_runner",
        "mutations_performed": False,
        "proposed_directories": [
            paths["runtime_root"], paths["incoming_dir"], paths["reports_dir"], paths["audit_dir"],
        ],
        "proposed_files": [paths["incoming_file"], paths["audit_log"], paths["activation_sentinel"]],
        "permissions": value["permissions"],
        "input_contract": value["input"],
        "output_contract": value["output"],
        "audit_contract": value["audit"],
        "retention_contract": value["retention"],
        "scheduler_contract": value["scheduler"],
        "execution_contract": value["execution"],
        "evidence_root": paths["evidence_root"],
        "blocked_reasons": [
            "policy_enabled_false",
            "deployment_authorized_false",
            "runner_implemented_false",
            "audit_append_disabled",
            "retention_disabled",
            "scheduler_disabled",
            "activation_sentinel_not_created_by_design",
        ],
        "safety": value["safety"],
    }
