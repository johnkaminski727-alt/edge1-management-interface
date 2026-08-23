#!/usr/bin/env python3
"""Serve the Big Bird telephony console and a bounded read-only status API."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
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
ANALYTICS_BASE_URL = "http://127.0.0.1:8099"
ANALYTICS_ROUTE_MAP = {
    "/api/telephony/analytics/health": "/api/telephony/platform/health",
    "/api/telephony/analytics/calls": "/api/telephony/platform/calls/summary",
    "/api/telephony/analytics/interconnects": "/api/telephony/platform/interconnects/summary",
}
ASTERISK_READ_ONLY_COMMANDS = {
    "channels": "core show channels count",
    "endpoints": "pjsip show endpoints",
    "contacts": "pjsip show contacts",
    "registrations": "pjsip show registrations",
    "transports": "pjsip show transports",
}

INTERCONNECT_REGISTRY = REPO_ROOT / "data/registry/interconnect/interconnect-registry.json"
PEER_STATUS = REPO_ROOT / "data/registry/interconnect/status/peer-status.json"
SIP_HISTORY = REPO_ROOT / "data/registry/interconnect/status/sip-options-history.json"
SIP_READINESS = REPO_ROOT / "reports/interconnect-readiness.json"
SIP_ACCEPTANCE = REPO_ROOT / "reports/interconnect/carrier-acceptance-report.md"


def load_json_file(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    return {}


def _carrier_lifecycle_map(registry: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for carrier in registry.get("carriers", []):
        carrier_id = carrier.get("id")
        if isinstance(carrier_id, str) and carrier_id:
            status = carrier.get("status")
            result[carrier_id] = status if isinstance(status, str) and status else "unknown"
    return result


def _peer_is_configured(peer: dict[str, Any], carrier_lifecycle: str) -> bool:
    endpoint = peer.get("endpoint")
    return (
        isinstance(endpoint, str)
        and bool(endpoint.strip())
        and endpoint.strip().lower() != "pending"
        and carrier_lifecycle not in {"planned", "pending"}
    )


def sip_interconnect_snapshot() -> list[dict[str, Any]]:
    registry = load_json_file(INTERCONNECT_REGISTRY)
    health = load_json_file(PEER_STATUS)
    peers = health.get("peers", {})
    carrier_lifecycle = _carrier_lifecycle_map(registry)
    result = []
    for peer in registry.get("sip_peers", []):
        carrier_status = carrier_lifecycle.get(peer.get("carrier_id"), "unknown")
        applicable = _peer_is_configured(peer, carrier_status)
        state = peers.get(peer.get("id"), {}) if isinstance(peers, dict) else {}
        options = state.get("sip_options", {}) if isinstance(state, dict) else {}
        result.append({
            "name": peer.get("id"),
            "status": state.get("status", "unknown") if applicable else "planned",
            "lifecycle": carrier_status,
            "health_check_applicable": applicable,
            "latency_ms": options.get("latency_ms") if applicable else None,
            "success_rate": 100 if applicable and options.get("response_code") == 200 else (0 if applicable else None),
            "active_calls": 0,
            "endpoint": peer.get("endpoint"),
        })
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
        result = subprocess.run(["pgrep", "-x", name], check=False, timeout=1.5, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def service_active(name: str) -> bool:
    if not name or not all(ch.isalnum() or ch in "@_.-" for ch in name):
        return False
    try:
        result = subprocess.run(["systemctl", "is-active", "--quiet", name], check=False, timeout=1.5, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def udp_listener_present(port: int) -> bool:
    try:
        result = subprocess.run(["ss", "-lun"], capture_output=True, text=True, check=False, timeout=1.5)
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


def _asterisk_cli(command: str) -> str | None:
    """Run one fixed read-only Asterisk CLI command and return bounded stdout."""
    if command not in ASTERISK_READ_ONLY_COMMANDS.values():
        raise ValueError("unsupported Asterisk read-only command")
    try:
        result = subprocess.run(
            ["asterisk", "-rx", command],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout[:250_000]


def _asterisk_counter(output: str | None, label: str) -> int:
    if not output:
        return 0
    match = re.search(rf"^\s*(\d+)\s+{re.escape(label)}\s*$", output, re.MULTILINE)
    return int(match.group(1)) if match else 0


def _pjsip_object_count(output: str | None, marker: str) -> int:
    if not output:
        return 0
    summaries = re.findall(r"^\s*Objects found:\s*(\d+)\s*$", output, re.MULTILINE)
    if summaries:
        return int(summaries[-1])
    prefix = f"{marker}:"
    return sum(1 for line in output.splitlines() if line.lstrip().startswith(prefix))


def asterisk_snapshot() -> dict[str, int | bool]:
    """Return privacy-minimized aggregate PBX/PJSIP counts from fixed local CLI reads."""
    outputs = {
        name: _asterisk_cli(command)
        for name, command in ASTERISK_READ_ONLY_COMMANDS.items()
    }
    return {
        "cli_available": any(value is not None for value in outputs.values()),
        "active_channels": _asterisk_counter(outputs["channels"], "active channels"),
        "active_calls": _asterisk_counter(outputs["channels"], "active calls"),
        "calls_processed": _asterisk_counter(outputs["channels"], "calls processed"),
        "endpoints": _pjsip_object_count(outputs["endpoints"], "Endpoint"),
        "contacts": _pjsip_object_count(outputs["contacts"], "Contact"),
        "outbound_registrations": _pjsip_object_count(outputs["registrations"], "Registration"),
        "transports": _pjsip_object_count(outputs["transports"], "Transport"),
    }


def asterisk_record(snapshot: dict[str, int | bool]) -> dict[str, Any]:
    process = process_running("asterisk")
    udp = udp_listener_present(5060)
    cli_available = bool(snapshot.get("cli_available"))
    healthy = process and udp and cli_available
    return {
        "id": "asterisk",
        "name": "Asterisk PBX",
        "role": "PBX and SIP application",
        "status": "healthy" if healthy else ("degraded" if process else "critical"),
        "latency_ms": None,
        "last_checked": utc_now(),
        "details": {
            "process_running": process,
            "udp_5060_listening": udp,
            "read_only_cli_available": cli_available,
            "active_channels": snapshot.get("active_channels", 0),
            "active_calls": snapshot.get("active_calls", 0),
            "endpoints": snapshot.get("endpoints", 0),
            "contacts": snapshot.get("contacts", 0),
            "outbound_registrations": snapshot.get("outbound_registrations", 0),
            "transports": snapshot.get("transports", 0),
        },
    }


def status_payload() -> dict[str, Any]:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    pbx = asterisk_snapshot()
    services = [
        asterisk_record(pbx),
        service_record("wwcx-numbering-node.service", "Numbering intelligence", 8093, "http://127.0.0.1:8093/healthz"),
        service_record("bigbird-ai-gateway.service", "Big Bird API gateway"),
    ]
    messaging_port = int(os.environ.get("WWCX_MESSAGING_PORT", "58080"))
    messaging_url = os.environ.get("WWCX_MESSAGING_HEALTH_URL", f"http://127.0.0.1:{messaging_port}/healthz")
    services.append(service_record("wwcx-messaging-gateway.service", "SMS and MMS gateway", messaging_port, messaging_url))
    healthy_count = sum(1 for item in services if item["status"] == "healthy")
    critical_count = sum(1 for item in services if item["status"] == "critical")
    interconnects = sip_interconnect_snapshot()
    operational_interconnects = [item for item in interconnects if item.get("health_check_applicable")]
    metrics = {
        "active_calls": pbx["active_calls"],
        "active_channels": pbx["active_channels"],
        "registrations": pbx["contacts"],
        "pbx_endpoints": pbx["endpoints"],
        "pbx_contacts": pbx["contacts"],
        "pbx_outbound_registrations": pbx["outbound_registrations"],
        "pbx_transports": pbx["transports"],
        "messages_queued": None,
        "trunks_healthy": sum(1 for item in operational_interconnects if item["status"] == "healthy"),
        "trunks_total": len(operational_interconnects),
        "trunks_planned": sum(1 for item in interconnects if not item.get("health_check_applicable")),
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
        "interconnects": interconnects,
        "registrations": [],
        "alerts": [{
            "severity": item["status"],
            "title": f"{item['name']} is {item['status']}",
            "summary": item["role"],
            "source": item["id"],
            "opened_at": utc_now(),
        } for item in services if item["status"] != "healthy"],
    }
    payload["fixture_available"] = bool(fixture)
    return payload


def _peer_acceptance_rows(registry: dict[str, Any], health: dict[str, Any]) -> list[dict[str, Any]]:
    carrier_lifecycle = _carrier_lifecycle_map(registry)
    health_peers = health.get("peers", {}) if isinstance(health.get("peers", {}), dict) else {}
    rows: list[dict[str, Any]] = []
    for peer in registry.get("sip_peers", []):
        peer_id = peer.get("id")
        lifecycle = carrier_lifecycle.get(peer.get("carrier_id"), "unknown")
        applicable = _peer_is_configured(peer, lifecycle)
        state = health_peers.get(peer_id, {}) if isinstance(peer_id, str) else {}
        options = state.get("sip_options", {}) if isinstance(state, dict) else {}
        rows.append({
            "peer": peer_id,
            "status": state.get("status", "unknown") if applicable else "planned",
            "options": options.get("response_code") if applicable else None,
            "latency_ms": options.get("latency_ms") if applicable else None,
            "health_check_applicable": applicable,
            "lifecycle": lifecycle,
        })
    return rows


def acceptance_payload() -> dict[str, Any]:
    registry = load_json_file(INTERCONNECT_REGISTRY)
    health = load_json_file(PEER_STATUS)
    peers = _peer_acceptance_rows(registry, health)
    return {
        "platform": "Edge1 SIP Interconnect",
        "carrier_count": len(registry.get("carriers", [])),
        "sip_peer_tests": peers,
        "routing_rules": len(registry.get("routing_rules", [])),
        "production_requirements": {
            "carrier_agreement": False,
            "sip_credentials": False,
            "public_signaling_endpoint": False,
            "emergency_calling": False,
            "stir_shaken": False,
        },
    }


def carrier_lifecycle_payload() -> dict[str, object]:
    registry = load_json_file(INTERCONNECT_REGISTRY)
    health = load_json_file(PEER_STATUS)
    health_peers = health.get("peers", {}) if isinstance(health.get("peers", {}), dict) else {}
    peer_definitions = registry.get("sip_peers", [])
    carriers = []
    for carrier in registry.get("carriers", []):
        carrier_id = carrier.get("id")
        lifecycle = carrier.get("status", "unknown")
        peer_states = []
        for peer in peer_definitions:
            if peer.get("carrier_id") != carrier_id:
                continue
            peer_id = peer.get("id")
            applicable = _peer_is_configured(peer, lifecycle if isinstance(lifecycle, str) else "unknown")
            state = health_peers.get(peer_id, {}) if isinstance(peer_id, str) else {}
            peer_states.append({
                "peer": peer_id,
                "status": state.get("status", "unknown") if applicable else "planned",
                "health_check_applicable": applicable,
            })
        carriers.append({
            "id": carrier_id,
            "name": carrier.get("name"),
            "status": lifecycle,
            "sip_peers": peer_states,
        })
    return {"carriers": carriers}


PORTAL_CARRIER_STATUS = REPO_ROOT / "data/registry/interconnect/portal/carrier-status.json"
PORTAL_SUMMARY = REPO_ROOT / "data/registry/interconnect/portal/public-summary.json"


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
        analytics_path = ANALYTICS_ROUTE_MAP.get(path)
        if analytics_path is not None:
            payload = http_json(ANALYTICS_BASE_URL + analytics_path)
            if payload is None:
                self.send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "analytics_unavailable"})
            else:
                self.send_json(HTTPStatus.OK, payload)
            return
        if path == "/api/telephony/status":
            self.send_json(HTTPStatus.OK, status_payload())
            return
        if path == "/api/telephony/health/history":
            self.send_json(HTTPStatus.OK, load_json_file(SIP_HISTORY))
            return
        if path == "/api/telephony/readiness":
            self.send_json(HTTPStatus.OK, load_json_file(SIP_READINESS))
            return
        if path == "/api/telephony/acceptance":
            self.send_json(HTTPStatus.OK, acceptance_payload())
            return
        if path == "/api/telephony/carriers":
            self.send_json(HTTPStatus.OK, carrier_lifecycle_payload())
            return
        if path == "/api/portal/carriers":
            self.send_json(HTTPStatus.OK, load_json_file(PORTAL_CARRIER_STATUS))
            return
        if path == "/api/portal/status":
            self.send_json(HTTPStatus.OK, load_json_file(PORTAL_SUMMARY))
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
