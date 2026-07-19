#!/usr/bin/env python3
"""Edge1 Operator MCP service scaffold.

Local/private service boundary for audited Edge1 operations.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

EVIDENCE_ROOT = Path(os.environ.get("EDGE1_OPERATOR_EVIDENCE", "/var/lib/edge1-operator/evidence"))
ALLOWED_ROOTS = [Path(p) for p in os.environ.get("EDGE1_OPERATOR_ROOTS", "/opt").split(":")]


def identity():
    return {
        "hostname": os.uname().nodename,
        "principal": os.environ.get("USER", "unknown"),
        "service": "edge1-operator-mcp",
    }


def evidence_id(command: str) -> str:
    value = f"{time.time()}:{command}".encode()
    return hashlib.sha256(value).hexdigest()[:16]


def run_bounded(command: list[str], timeout: int = 30):
    eid = evidence_id(" ".join(command))
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    return {
        "execution_id": eid,
        "identity": identity(),
        "command": command,
        "exit_code": result.returncode,
        "stdout": result.stdout[-10000:],
        "stderr": result.stderr[-10000:],
        "completed": True,
    }


def main():
    print(json.dumps({"status": "ready", "identity": identity()}))


if __name__ == "__main__":
    main()
