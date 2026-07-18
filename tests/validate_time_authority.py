#!/usr/bin/env python3
"""Validate the WW.CX Time Authority collectors, API, fixtures, and UI."""

from __future__ import annotations

import importlib.util
import csv
import io
import json
import socket
import struct
import tempfile
import threading
import time
import os
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


collector = load_module("ntp_rtt_probe", COLLECTOR_PATH)
dashboard = load_module("time_authority_server", SERVER_PATH)


class FakeNtpServer:
    def __init__(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.port = self.sock.getsockname()[1]
        self.thread = threading.Thread(target=self.run, daemon=True)

    def start(self) -> None:
        self.thread.start()

    def run(self) -> None:
        request, address = self.sock.recvfrom(512)
        response = bytearray(48)
        response[0] = 0x24  # LI=0, VN=4, mode=4
        response[1] = 1
        response[2] = 6
        response[3] = 0xEC
        response[4:8] = struct.pack("!I", 0)
        response[8:12] = struct.pack("!I", 1)
        response[12:16] = b"PPS\0"
        response[24:32] = request[40:48]
        now = collector.encode_ntp_timestamp(time.time())
        response[32:40] = now
        response[40:48] = now
        self.sock.sendto(response, address)
        self.sock.close()

    def close(self) -> None:
        self.thread.join(timeout=3)


def validate_catalogs() -> None:
    sources = collector.load_sources(ROOT / "modules" / "time-authority" / "config" / "sources.json")
    assert len(sources) == 5
    assert len({item["source_id"] for item in sources}) == 5
    assert {item["server_name"] for item in sources} == {
        "sth1.ntp.se", "sth2.ntp.se", "mmo1.ntp.se", "time.nist.gov", "time.cloudflare.com"
    }

    baseline = json.loads(
        (ROOT / "modules" / "time-authority" / "fixtures" / "baseline-measurements.json").read_text(encoding="utf-8")
    )
    assert len(baseline["records"]) == 10
    assert {item["observer_id"] for item in baseline["records"]} == {"edge1", "shared-host"}


def validate_probe() -> None:
    probe_text = COLLECTOR_PATH.read_text(encoding="utf-8")
    assert "from __future__ import annotations" not in probe_text
    assert "socket.socket | None" not in probe_text
    for unsupported in ("dict[", "list[", "tuple[", "set["):
        assert unsupported not in probe_text

    fake = FakeNtpServer()
    fake.start()
    record = collector.probe_source(
        {
            "source_id": "test-pps",
            "server_name": "127.0.0.1",
            "port": fake.port,
            "provider": "test",
            "expected_stratum": 1,
            "expected_refids": ["PPS"],
        },
        observer_id="test-observer",
        observer_host="test.example",
        timeout=2,
    )
    fake.close()
    assert record["reachable"] is True
    assert record["stratum"] == 1
    assert record["refid"] == "PPS"
    assert record["expectation_ok"] is True
    assert record["rtt_ms"] >= 0

    with tempfile.TemporaryDirectory() as raw_tmp:
        output = Path(raw_tmp) / "measurements.jsonl"
        collector.append_jsonl(output, [record, record])
        assert len(output.read_text(encoding="utf-8").splitlines()) == 2


def validate_dashboard() -> None:
    mode, records = dashboard.load_records([], 500)
    assert mode == "baseline"
    assert len(records) == 10
    payload = dashboard.summary_payload(500)
    assert payload["schema_version"] == 1
    assert len(payload["latest"]) == 10
    assert len(payload["observers"]) == 2
    assert dashboard.clamp_limit("1") == 10
    assert dashboard.clamp_limit("99999") == 5000
    csv_rows = list(csv.DictReader(io.StringIO(dashboard.csv_payload(payload["history"]).decode("utf-8"))))
    assert len(csv_rows) == 10
    assert csv_rows[0]["Observer ID"] in {"edge1", "shared-host"}
    assert csv_rows[0]["Server Name"]
    handler_text = SERVER_PATH.read_text(encoding="utf-8")
    for header in ("Content-Security-Policy", "Permissions-Policy", "X-Frame-Options", "X-Content-Type-Options"):
        assert header in handler_text


def validate_web() -> None:
    web = ROOT / "src" / "web" / "time-authority"
    for relative in ("index.html", "app.js", "styles.css", "fixtures/baseline-summary.json"):
        assert (web / relative).is_file(), f"missing web asset: {relative}"
    html = (web / "index.html").read_text(encoding="utf-8")
    for required_id in ("summary-cards", "observer-filter", "rtt-chart", "measurement-rows"):
        assert f'id="{required_id}"' in html
    assert "/api/time-authority/export.csv?limit=5000" in html
    fixture = json.loads((web / "fixtures" / "baseline-summary.json").read_text(encoding="utf-8"))
    assert fixture["mode"] == "baseline"
    assert len(fixture["latest"]) == 10


def validate_deployment_assets() -> None:
    deploy = ROOT / "deploy"
    required_executables = (
        "install-time-authority-edge1.sh",
        "install-time-authority-shared-host.sh",
        "time-authority-edge1-preflight.sh",
        "time-authority-edge1-smoke-test.sh",
        "time-authority-shared-host-smoke-test.sh",
    )
    for relative in required_executables:
        path = deploy / relative
        assert path.is_file(), relative
        assert os.access(path, os.X_OK), relative

    shared_installer = (deploy / "install-time-authority-shared-host.sh").read_text(encoding="utf-8")
    assert "WWCX_TIME_AUTHORITY_INSTALL_CRON" in shared_installer
    assert "crontab -" in shared_installer
    assert "time-authority-shared-host-smoke-test.sh" in shared_installer

    edge_installer = (deploy / "install-time-authority-edge1.sh").read_text(encoding="utf-8")
    assert "time-authority-edge1-preflight.sh" in edge_installer
    assert "time-authority-edge1-smoke-test.sh" in edge_installer

    dashboard_unit = (deploy / "systemd" / "edge1-time-authority-dashboard.service").read_text(encoding="utf-8")
    for directive in ("NoNewPrivileges=true", "ProtectSystem=strict", "127.0.0.1", "MemoryDenyWriteExecute=true"):
        assert directive in dashboard_unit

    workflow = ROOT / ".github" / "workflows" / "validate.yml"
    assert workflow.is_file()
    assert "python:3.6.15-slim-buster" in workflow.read_text(encoding="utf-8")


def main() -> int:
    validate_catalogs()
    validate_probe()
    validate_dashboard()
    validate_web()
    validate_deployment_assets()
    print("time authority validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
