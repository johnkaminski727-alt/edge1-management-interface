#!/usr/bin/env python3
"""Return bounded Asterisk diagnostics for the Edge1 Operations API.

Prefer the fresh snapshot produced by the Asterisk-owned fixed-command helper.
If that evidence is missing, stale, malformed, or fails closed metadata checks,
fall back to the existing direct/passive Control Surfaces diagnostic path.
"""
from __future__ import annotations

import grp
import json
import os
import pwd
import stat
import time
from pathlib import Path

import control_surface_diagnostics as base

SNAPSHOT_PATH = Path("/run/edge1-asterisk-diagnostics/status.json")
SNAPSHOT_CONTRACT = "wwcx.edge1-asterisk-readonly-snapshot.v1"
MAX_SNAPSHOT_AGE_SECONDS = 90
MAX_CLOCK_SKEW_SECONDS = 5
EXPECTED_COMMAND_IDS = tuple(
    f"asterisk.{name}" for name, _argv in base.PROFILES["asterisk"]
)


def expected_snapshot_identity() -> tuple[int, int]:
    return pwd.getpwnam("asterisk").pw_uid, grp.getgrnam("bigbird-audit").gr_gid


def load_native_snapshot(
    path: Path = SNAPSHOT_PATH,
    *,
    now: float | None = None,
) -> tuple[dict | None, str | None]:
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode):
            return None, "snapshot_not_regular"
        if stat.S_IMODE(info.st_mode) != 0o640:
            return None, "snapshot_mode_drift"
        expected_uid, expected_gid = expected_snapshot_identity()
        if info.st_uid != expected_uid or info.st_gid != expected_gid:
            return None, "snapshot_owner_group_drift"

        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            return None, "snapshot_not_object"
        if value.get("contract") != SNAPSHOT_CONTRACT:
            return None, "snapshot_contract_drift"
        if value.get("read_only") is not True or value.get("parameters_accepted") is not False:
            return None, "snapshot_safety_contract_drift"
        if value.get("status") != "ok":
            return None, "snapshot_native_status_not_ok"
        if tuple(value.get("command_ids") or ()) != EXPECTED_COMMAND_IDS:
            return None, "snapshot_command_contract_drift"

        generated = value.get("generated_at_epoch")
        if not isinstance(generated, (int, float)):
            return None, "snapshot_timestamp_missing"
        current = time.time() if now is None else now
        age = current - float(generated)
        if age < -MAX_CLOCK_SKEW_SECONDS:
            return None, "snapshot_timestamp_in_future"
        if age > MAX_SNAPSHOT_AGE_SECONDS:
            return None, "snapshot_stale"

        checks = value.get("checks")
        if not isinstance(checks, list) or len(checks) != len(EXPECTED_COMMAND_IDS):
            return None, "snapshot_check_count_drift"
        if tuple(item.get("argv_id") for item in checks if isinstance(item, dict)) != EXPECTED_COMMAND_IDS:
            return None, "snapshot_check_contract_drift"
        if any(not isinstance(item, dict) or item.get("status") != "ok" for item in checks):
            return None, "snapshot_check_failed"

        return {
            "component": "asterisk",
            "status": "ok",
            "native_cli_status": "ok",
            "native_diagnostic_source": "asterisk-owned-fixed-snapshot",
            "read_only": True,
            "checks": checks,
            "passive_fallback": None,
            "snapshot": {
                "contract": SNAPSHOT_CONTRACT,
                "generated_at": value.get("generated_at"),
                "age_seconds": max(0, int(age)),
                "owner": "asterisk",
                "reader_group": "bigbird-audit",
                "mode": "0640",
                "parameters_accepted": False,
            },
        }, None
    except (FileNotFoundError, KeyError, OSError, ValueError, json.JSONDecodeError):
        return None, "snapshot_unavailable_or_invalid"


def diagnostics() -> dict:
    snapshot, reason = load_native_snapshot()
    if snapshot is not None:
        return snapshot

    fallback = base.component("asterisk")
    fallback["native_diagnostic_source"] = "direct-operations-api-with-passive-fallback"
    fallback["bounded_snapshot_status"] = reason
    return fallback


def main() -> None:
    print(json.dumps(diagnostics(), sort_keys=True, separators=(",", ":"), ensure_ascii=False))


if __name__ == "__main__":
    main()
