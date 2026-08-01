#!/usr/bin/env python3
"""Verify the Phase A smoke test tolerates normal systemd startup latency."""

from __future__ import annotations

import os
import pathlib
import shlex
import socket
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER = ROOT / "server/outbound_mail_gateway_server.py"
CONFIG = ROOT / "config/messaging/outbound-mail-gateway.json"
IDENTITIES = ROOT / "config/messaging/mail-identities.json"
SMOKE = ROOT / "deploy/messaging/outbound-mail-gateway-smoke-test.sh"


def reserve_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


port = reserve_port()
server_command = [
    sys.executable,
    str(SERVER),
    "--config",
    str(CONFIG),
    "--identities",
    str(IDENTITIES),
    "--host",
    "127.0.0.1",
    "--port",
    str(port),
]
launcher_command = "sleep 2; exec " + " ".join(shlex.quote(item) for item in server_command)
launcher = subprocess.Popen(
    ["sh", "-c", launcher_command],
    cwd=ROOT,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.PIPE,
    text=True,
)
try:
    environment = os.environ.copy()
    environment.update(
        {
            "HOST": "127.0.0.1",
            "PORT": str(port),
            "READY_ATTEMPTS": "8",
            "READY_DELAY_SECONDS": "1",
        }
    )
    result = subprocess.run(
        ["sh", str(SMOKE)],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Outbound mail gateway disabled-state smoke test passed" in result.stdout
    assert "Preparation API: disabled" in result.stdout
    assert "External delivery: rejected" in result.stdout
    attempts_line = next(
        line for line in result.stdout.splitlines() if line.startswith("Readiness attempts used:")
    )
    attempts = int(attempts_line.rsplit(":", 1)[1].strip())
    assert attempts >= 2, attempts
finally:
    launcher.terminate()
    try:
        launcher.wait(timeout=5)
    except subprocess.TimeoutExpired:
        launcher.kill()
        launcher.wait(timeout=5)

print("Outbound mail smoke readiness validation passed")
print("Delayed service startup is retried before no-send checks run")
