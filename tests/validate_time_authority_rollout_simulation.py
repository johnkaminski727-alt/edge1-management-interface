#!/usr/bin/env python3
"""Simulate both Time Authority production rollouts without host mutation."""

from __future__ import annotations

import csv
import importlib.util
import json
import os
import pwd
import socket
import struct
import subprocess
import tempfile
import threading
import time
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COLLECTOR_PATH = ROOT / "tools" / "time_authority" / "ntp_rtt_probe.py"
SERVER_PATH = ROOT / "server" / "time_authority_server.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


collector = load_module("rollout_ntp_probe", COLLECTOR_PATH)
dashboard = load_module("rollout_time_authority_server", SERVER_PATH)


class FakeNtpServer:
    def __init__(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.settimeout(0.2)
        self.port = self.sock.getsockname()[1]
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)

    def start(self) -> None:
        self.thread.start()

    def run(self) -> None:
        while not self.stop.is_set():
            try:
                request, address = self.sock.recvfrom(512)
            except socket.timeout:
                continue
            except OSError:
                break
            if len(request) < 48:
                continue
            response = bytearray(48)
            response[0] = 0x24
            response[1] = 1
            response[2] = 6
            response[3] = 0xEC
            response[8:12] = struct.pack("!I", 1)
            response[12:16] = b"PPS\0"
            response[24:32] = request[40:48]
            now = collector.encode_ntp_timestamp(time.time())
            response[32:40] = now
            response[40:48] = now
            self.sock.sendto(response, address)

    def close(self) -> None:
        self.stop.set()
        self.sock.close()
        self.thread.join(timeout=3)


def write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def make_fake_commands(root: Path) -> tuple[Path, Path]:
    fake_bin = root / "fake-bin"
    fake_bin.mkdir()
    crontab_file = root / "crontab.txt"
    write_executable(
        fake_bin / "systemctl",
        """#!/bin/sh
set -eu
case "$*" in
  "start edge1-time-authority-collector.service")
    exec "$EDGE1_MANAGEMENT_ROOT/tools/time_authority/collect-edge1.sh" >/dev/null
    ;;
  *) exit 0 ;;
esac
""",
    )
    write_executable(
        fake_bin / "crontab",
        """#!/bin/sh
set -eu
case "${1:-}" in
  -l)
    test -f "$FAKE_CRONTAB_FILE" || exit 1
    cat "$FAKE_CRONTAB_FILE"
    ;;
  -)
    cat >"$FAKE_CRONTAB_FILE"
    ;;
  *) exit 2 ;;
esac
""",
    )
    return fake_bin, crontab_file


def run_checked(command: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True, check=False)
    if result.returncode:
        raise AssertionError(
            f"command failed ({result.returncode}): {' '.join(command)}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    ntp = FakeNtpServer()
    ntp.start()
    httpd = None
    try:
        with tempfile.TemporaryDirectory(prefix="wwcx-time-rollout-") as raw_tmp:
            temp_root = Path(raw_tmp)
            sources = temp_root / "sources.json"
            sources.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "sources": [
                            {
                                "source_id": "simulation-pps",
                                "server_name": "127.0.0.1",
                                "port": ntp.port,
                                "provider": "WW.CX simulation",
                                "region": "local test",
                                "expected_stratum": 1,
                                "expected_refids": ["PPS"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            fake_bin, crontab_file = make_fake_commands(temp_root)
            base_env = os.environ.copy()
            base_env["PATH"] = str(fake_bin) + os.pathsep + base_env["PATH"]
            base_env["FAKE_CRONTAB_FILE"] = str(crontab_file)

            edge_data_dir = temp_root / "edge-data"
            edge_output = edge_data_dir / "measurements.jsonl"
            edge_units = temp_root / "systemd-units"
            os.environ["EDGE1_TIME_AUTHORITY_DATA_PATHS"] = str(edge_output)
            httpd = dashboard.ThreadingHTTPServer(("127.0.0.1", 0), dashboard.TimeAuthorityHandler)
            http_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            http_thread.start()
            base_url = f"http://127.0.0.1:{httpd.server_address[1]}"

            edge_env = dict(base_env)
            edge_env.update(
                {
                    "EDGE1_MANAGEMENT_ROOT": str(ROOT),
                    "EDGE1_TIME_AUTHORITY_USER": pwd.getpwuid(os.getuid()).pw_name,
                    "EDGE1_TIME_AUTHORITY_DATA_DIR": str(edge_data_dir),
                    "EDGE1_TIME_AUTHORITY_OUTPUT": str(edge_output),
                    "EDGE1_TIME_AUTHORITY_SOURCES": str(sources),
                    "EDGE1_TIME_AUTHORITY_UNIT_DIR": str(edge_units),
                    "EDGE1_TIME_AUTHORITY_SYSTEMCTL": str(fake_bin / "systemctl"),
                    "EDGE1_TIME_AUTHORITY_BASE_URL": base_url,
                    "EDGE1_TIME_AUTHORITY_SIMULATION": "1",
                }
            )
            unsafe_edge_env = dict(edge_env)
            unsafe_edge_env["EDGE1_TIME_AUTHORITY_SYSTEMCTL"] = "systemctl"
            unsafe_result = subprocess.run(
                [str(ROOT / "deploy" / "install-time-authority-edge1.sh")],
                cwd=ROOT,
                env=unsafe_edge_env,
                text=True,
                capture_output=True,
                check=False,
            )
            assert unsafe_result.returncode != 0
            assert "explicit non-production EDGE1_TIME_AUTHORITY_SYSTEMCTL" in unsafe_result.stderr

            edge_result = run_checked([str(ROOT / "deploy" / "install-time-authority-edge1.sh")], edge_env)
            assert "installed on Edge1" in edge_result.stdout
            installed_units = sorted(path.name for path in edge_units.iterdir())
            assert installed_units == [
                "edge1-time-authority-collector.service",
                "edge1-time-authority-collector.timer",
                "edge1-time-authority-dashboard.service",
            ]
            edge_records = read_jsonl(edge_output)
            assert len(edge_records) == 2
            assert all(item["observer_id"] == "edge1" and item["reachable"] for item in edge_records)
            with urllib.request.urlopen(base_url + "/api/time-authority/export.csv?limit=5000", timeout=3) as response:
                assert response.headers.get_content_type() == "text/csv"
                csv_lines = response.read().decode("utf-8").splitlines()
            csv_rows = list(csv.DictReader(csv_lines))
            assert len(csv_rows) == 2
            assert all(item["Observer ID"] == "edge1" for item in csv_rows)

            shared_home = temp_root / "shared-home"
            shared_home.mkdir()
            shared_root = shared_home / "wwcx-time-authority"
            shared_private = shared_home / "private" / "wwcx-time-authority"
            shared_output = shared_private / "measurements.jsonl"
            shared_env = dict(base_env)
            shared_env.update(
                {
                    "HOME": str(shared_home),
                    "WWCX_TIME_AUTHORITY_ROOT": str(shared_root),
                    "WWCX_TIME_AUTHORITY_PRIVATE": str(shared_private),
                    "WWCX_TIME_AUTHORITY_OUTPUT": str(shared_output),
                    "WWCX_TIME_AUTHORITY_PYTHON": "python3",
                    "WWCX_TIME_AUTHORITY_SOURCES_FILE": str(sources),
                    "WWCX_TIME_AUTHORITY_INSTALL_CRON": "1",
                }
            )
            shared_installer = str(ROOT / "deploy" / "install-time-authority-shared-host.sh")
            first_shared = run_checked([shared_installer], shared_env)
            second_shared = run_checked([shared_installer], shared_env)
            assert "installed and verified" in first_shared.stdout
            assert "installed and verified" in second_shared.stdout
            cron_lines = [line for line in crontab_file.read_text(encoding="utf-8").splitlines() if line.strip()]
            assert len(cron_lines) == 1
            assert "*/15 * * * *" in cron_lines[0]
            assert str(shared_root / "collect-shared-host.sh") in cron_lines[0]
            shared_records = read_jsonl(shared_output)
            assert len(shared_records) == 2
            assert all(item["observer_id"] == "shared-host" and item["reachable"] for item in shared_records)
            assert (shared_root / "ntp_rtt_probe.py").stat().st_mode & 0o777 == 0o700
            assert (shared_root / "sources.json").stat().st_mode & 0o777 == 0o600

            print("Edge1 simulation: safety guard, 3 units, 2 live measurements, CSV export verified")
            print("Shared-host simulation: repeat install, 1 cron line, 2 live measurements, permissions verified")
            print("time authority rollout simulation passed")
    finally:
        if httpd is not None:
            httpd.shutdown()
            httpd.server_close()
        ntp.close()
        os.environ.pop("EDGE1_TIME_AUTHORITY_DATA_PATHS", None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
