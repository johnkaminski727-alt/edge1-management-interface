#!/usr/bin/env python3
"""Render the disabled telephony report runtime design without host mutation."""
from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))

from telephony_report_runtime_policy import (  # noqa: E402
    MAX_POLICY_BYTES,
    RuntimePolicyError,
    canonical_json,
    runtime_plan,
)

DEFAULT_POLICY = ROOT / "config" / "telephony" / "analytics-report-runtime-policy.json"


def read_policy(path: Path) -> dict[str, Any]:
    if not path.is_absolute():
        raise RuntimePolicyError("policy path must be absolute")
    if path.is_symlink():
        raise RuntimePolicyError("policy path must not be a symlink")
    try:
        fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    except OSError as exc:
        raise RuntimePolicyError(f"could not open policy: {exc}") from exc
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode):
            raise RuntimePolicyError("policy must be a regular file")
        if metadata.st_size > MAX_POLICY_BYTES:
            raise RuntimePolicyError("policy exceeds the accepted size limit")
        data = os.read(fd, MAX_POLICY_BYTES + 1)
        if len(data) > MAX_POLICY_BYTES:
            raise RuntimePolicyError("policy exceeds the accepted size limit")
    finally:
        os.close(fd)
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimePolicyError("policy must be one UTF-8 JSON document") from exc
    if not isinstance(value, dict):
        raise RuntimePolicyError("policy JSON must be an object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate and print the design-only telephony report runtime plan."
    )
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    args = parser.parse_args()
    try:
        plan = runtime_plan(read_policy(args.policy))
    except RuntimePolicyError as exc:
        parser.error(str(exc))
    print(canonical_json(plan))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
