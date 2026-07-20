#!/usr/bin/env python3
"""Serve the Big Bird telephony console and a bounded read-only status API."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import socket
import subprocess
import urllib.request
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = REPO_ROOT / "src" / "web" / "telephony"
FIXTURE = WEB_ROOT / "telephony.fixture.json"
LOOPBACK_HOST = "127.0.0.1"

INTERCONNECT_REGISTRY = (
    REPO_ROOT /
    "data/registry/interconnect/interconnect-registry.json"
)

PEER_STATUS = (
    REPO_ROOT /
    "data/registry/interconnect/status/peer-status.json"
)

SIP_HISTORY = (
    REPO_ROOT /
    "data/registry/interconnect/status/sip-options-history.json"
)

SIP_READINESS = (
    REPO_ROOT /
    "reports/interconnect-readiness.json"
)


def load_json_file(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    return {}


def sip_interconnect_snapshot() -> list[dict[str, Any]]:
    registry = load_json_file(INTERCONNECT_REGISTRY)
    health = load_json_file(PEER_STATUS)

    peers = health.get("peers", {})
    result = []

    for peer in registry.get("sip_peers", []):

        state = peers.get(
            peer.get("id"),
            {}
        )

        options = state.get(
            "sip_options",
            {}
        )

        result.append(
            {
                "name": peer.get("id"),
                "status": state.get(
                    "status",
                    "unknown"
                ),
                "latency_ms": options.get(
                    "latency_ms"
                ),
                "success_rate": (
                    100
                    if options.get("response_code") == 200
                    else 0
                ),
                "active_calls": 0,
                "endpoint": peer.get("endpoint"),
            }
        )

    return result


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def tcp_probe(host: str, port: int, timeout: float = 0.8) -> tuple[bool, int | None]:
    started = dt.datetime.now(dt.timezone.utc)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            elapsed = (dt.datetime.now(dt.timezone.utc) - started).total_seconds() * 1000
            return True, max(0, round(elapsed))
    except OSError:
        return False, None


def http_json(url: str, timeout: float = 1.2) -> dict[str, Any] | None:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "big-bird-telephony-status/1"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            length = int(response.headers.get("Content-Length", "0") or 0)
            if response.status != 200 or length > 1_000_000:
                return None
            value = json.loads(response.read(1_000_001).decode("utf-8"))
            return value if isinstance(value, dict) else None
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def process_running(name: str) -> bool:
    try:
        result = subprocess.run(
            ["pgrep", "-x", name],
            check=False,
            timeout=1.5,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def service_active(name: str) -> bool:
    if not name or not all(ch.isalnum() or ch in "@_.-" for ch in name):
        return False
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "--quiet", name],
            check=False,
            timeout=1.5,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def udp_listener_present(port: int) -> bool:
    try:
        result = subprocess.run(
            ["ss", "-lun"],
            capture_output=True,
            text=True,
            check=False,
            timeout=1.5,
        )
        suffix = f":{port}"
        return any(suffix in line for line in result.stdout.splitlines())
    except (OSError, subprocess.TimeoutExpired):
        return False


def service_record(name: str, role: str, port: int | None = None, health_url: str | None = None) -> dict[str, Any]:
    active = service_active(name)
    reachable, latency = (tcp_probe(LOOPBACK_HOST, port) if port else (active, None))
    health = http_json(health_url) if health_url else None
    healthy = active and reachable and (health is not None if health_url else True)
    return {
        "id": name,
        "name": name,
        "role": role,
        "status": "healthy" if healthy else ("degraded" if active else "critical"),
        "latency_ms": latency,
        "last_checked": utc_now(),
        "details": {"service_active": active, "listener_reachable": reachable, "health": health},
    }


def asterisk_record() -> dict[str, Any]:
    process = process_running("asterisk")
    udp = udp_listener_present(5060)
    healthy = process and udp
    return {
        "id": "asterisk",
        "name": "Asterisk PBX",
        "role": "PBX and SIP application",
        "status": "healthy" if healthy else ("degraded" if process else "critical"),
        "latency_ms": None,
        "last_checked": utc_now(),
        "details": {"process_running": process, "udp_5060_listening": udp},
    }


def asterisk_snapshot() -> tuple[int, int]:
    """Return active call and endpoint counts when the local CLI is permitted."""
    try:
        channels = subprocess.run(
            ["asterisk", "-rx", "core show channels concise"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        endpoints = subprocess.run(
            ["asterisk", "-rx", "pjsip show endpoints"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        channel_lines = [line for line in channels.stdout.splitlines() if line.strip()]
        active_calls = len(channel_lines) // 2
        registrations = sum(1 for line in endpoints.stdout.splitlines() if line.lstrip().startswith("Endpoint:"))
        return active_calls, registrations
    except (OSError, subprocess.TimeoutExpired):
        return 0, 0


def status_payload() -> dict[str, Any]:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    services = [
        asterisk_record(),
        service_record(
            "wwcx-numbering-node.service",
            "Numbering intelligence",
            8093,
            "http://127.0.0.1:8093/healthz",
        ),
        service_record("bigbird-ai-gateway.service", "Big Bird API gateway"),
    ]
    messaging_url = os.environ.get("WWCX_MESSAGING_HEALTH_URL", "http://127.0.0.1:8095/healthz")
    services.append(service_record("wwcx-messaging-gateway.service", "SMS and MMS gateway", 8095, messaging_url))

    active_calls, registrations = asterisk_snapshot()
    healthy_count = sum(1 for item in services if item["status"] == "healthy")
    critical_count = sum(1 for item in services if item["status"] == "critical")

    metrics = {
        "active_calls": active_calls,
        "registrations": registrations,
        "messages_queued": None,
        "trunks_healthy": sum(
            1 for item in sip_interconnect_snapshot()
            if item["status"] == "healthy"
        ),
        "trunks_total": len(
            sip_interconnect_snapshot()
        ),
        "critical_alerts": critical_count,
    }
    payload = {
        "schema_version": 1,
        "generated_at": utc_now(),
        "mode": "live_read_only",
        "site": socket.getfqdn(),
        "overall_status": "critical" if critical_count else ("degraded" if healthy_count < len(services) else "healthy"),
        "metrics": metrics,
        "services": services,
        "interconnects": sip_interconnect_snapshot(),
        "registrations": [],
        "alerts": [
            {
                "severity": item["status"],
                "title": f"{item['name']} is {item['status']}",
                "summary": item["role"],
                "source": item["id"],
                "opened_at": utc_now(),
            }
            for item in services
            if item["status"] != "healthy"
        ],
    }
    payload["fixture_available"] = bool(fixture)
    return payload


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; base-uri 'none'; frame-ancestors 'none'")
        self.send_header("Permissions-Policy", "camera=(), geolocation=(), microphone=()")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/api/telephony/status":
            self.send_json(HTTPStatus.OK, status_payload())
            return

        if path == "/api/telephony/health/history":
            self.send_json(
                HTTPStatus.OK,
                load_json_file(SIP_HISTORY)
            )
            return

        if path == "/api/telephony/readiness":
            self.send_json(
                HTTPStatus.OK,
                load_json_file(SIP_READINESS)
            )
            return
        if path == "/healthz":
            self.send_json(HTTPStatus.OK, {"status": "ok", "time": utc_now()})
            return
        super().do_GET()

    def send_json(self, status: HTTPStatus, value: dict[str, Any]) -> None:
        body = json.dumps(value, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=LOOPBACK_HOST)
    parser.add_argument("--port", type=int, default=8096)
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "::1", "localhost"}:
        parser.error("telephony status server must remain loopback-only")
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
