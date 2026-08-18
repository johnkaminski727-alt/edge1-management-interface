#!/usr/bin/env python3
"""Bounded read-only diagnostics for WW.CX Edge1 Control Surfaces.

This program intentionally accepts only a fixed diagnostic profile. It never
accepts a shell fragment, arbitrary command, backend URL, port, file path, or
Asterisk/Kamailio command from a caller.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import shutil
import subprocess
import time
from collections import Counter

MAX_OUTPUT = 12000
MAX_LISTENERS = 500
PATH = "/usr/sbin:/usr/bin:/sbin:/bin"

SECRET_PATTERNS = (
    re.compile(r"(?i)\b(password|passwd|secret|token|api[_ -]?key|private[_ -]?key|preshared[_ -]?key)\b\s*[:=]\s*\S+"),
    re.compile(r"(?i)\b(authorization:)\s*\S+"),
)
LONG_VALUE = re.compile(r"\b[A-Za-z0-9+/=_-]{64,}\b")
PROCESS_NAME = re.compile(r'\(\("([^"]+)"')

PROFILES = {
    "asterisk": (
        ("core_uptime", ("asterisk", "-rx", "core show uptime")),
        ("core_channels", ("asterisk", "-rx", "core show channels")),
        ("pjsip_endpoints", ("asterisk", "-rx", "pjsip show endpoints")),
        ("pjsip_transports", ("asterisk", "-rx", "pjsip show transports")),
        ("pjsip_registrations", ("asterisk", "-rx", "pjsip show registrations")),
        ("modules", ("asterisk", "-rx", "module show")),
        ("http_status", ("asterisk", "-rx", "http show status")),
    ),
    "kamailio": (
        ("version", ("kamcmd", "core.version")),
        ("uptime", ("kamcmd", "core.uptime")),
        ("processes", ("kamcmd", "core.ps")),
    ),
    "freepbx": (
        ("status", ("fwconsole", "status")),
    ),
}


def clean(value: str) -> str:
    text = value.replace("\x00", "")
    for pattern in SECRET_PATTERNS:
        text = pattern.sub(lambda match: f"{match.group(1)}=[REDACTED]", text)
    text = LONG_VALUE.sub("[REDACTED-LONG-VALUE]", text)
    return text[-MAX_OUTPUT:]


def run_fixed(argv: tuple[str, ...], timeout: int = 20) -> dict:
    executable = shutil.which(argv[0], path=PATH)
    if executable is None:
        return {
            "available": False,
            "status": "command_unavailable",
            "exit_code": None,
            "duration_ms": 0,
            "stdout": "",
            "stderr": "",
        }
    started = time.monotonic()
    try:
        result = subprocess.run(
            list(argv),
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
            env={"PATH": PATH, "LANG": "C", "LC_ALL": "C"},
        )
    except subprocess.TimeoutExpired as exc:
        duration = int((time.monotonic() - started) * 1000)
        return {
            "available": True,
            "status": "timed_out",
            "exit_code": None,
            "duration_ms": duration,
            "stdout": clean(exc.stdout or ""),
            "stderr": clean(exc.stderr or ""),
        }
    duration = int((time.monotonic() - started) * 1000)
    return {
        "available": True,
        "status": "ok" if result.returncode == 0 else "failed",
        "exit_code": result.returncode,
        "duration_ms": duration,
        "stdout": clean(result.stdout),
        "stderr": clean(result.stderr),
    }


def split_host_port(value: str) -> tuple[str, int | None]:
    value = value.strip()
    if value.startswith("[") and "]:" in value:
        host, port_text = value[1:].rsplit("]:", 1)
    elif ":" in value:
        host, port_text = value.rsplit(":", 1)
    else:
        return value, None
    if port_text == "*":
        return host, None
    try:
        return host, int(port_text)
    except ValueError:
        return host, None


def is_loopback(host: str) -> bool:
    normalized = host.split("%", 1)[0].strip("[]")
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def exposure_for(host: str) -> str:
    normalized = host.split("%", 1)[0].strip("[]")
    if is_loopback(normalized):
        return "loopback"
    if normalized in {"0.0.0.0", "::", "*", ""}:
        return "wildcard"
    return "specific"


def classify_listener(protocol: str, host: str, port: int | None, process: str) -> tuple[str, str]:
    proc = process.lower()
    loopback = is_loopback(host)

    if proc in {"sshd", "ssh"} or port == 22:
        return "private-control", "SSH administration"
    if proc in {"mysqld", "mariadbd", "postgres", "postgresql"} or port in {3306, 5432}:
        return "private-control", "database listener"
    if proc in {"node", "nodejs"} and not loopback:
        return "private-control", "non-loopback Node service requires management attribution"
    if proc == "asterisk" and port in {5038, 8088, 8089}:
        return "private-control", "Asterisk management/HTTP listener"
    if loopback:
        if proc in {"asterisk", "fwconsole", "httpd", "apache2"}:
            return "private-control", "loopback management surface"
        return "internal-service", "loopback-only listener"
    if proc in {"apache2", "httpd", "nginx"} and port in {80, 443}:
        return "public-infrastructure", "public HTTP/HTTPS listener"
    if proc == "kamailio" and port in {5060, 5061}:
        return "peering", "Kamailio SIP signaling"
    if proc in {"chronyd", "ntpd", "ntpsec", "systemd-timesyncd"} and protocol == "udp" and port == 123:
        return "public-infrastructure", "NTP service"
    if proc == "asterisk" and port in {5060, 5061}:
        return "unknown-needs-attribution", "Asterisk non-loopback SIP listener requires peering dependency review"
    return "unknown-needs-attribution", "owner/purpose/consumers require attribution"


def parse_ss_line(line: str) -> dict | None:
    parts = line.split(None, 6)
    if len(parts) < 6:
        return None
    protocol = parts[0].lower()
    local = parts[4]
    host, port = split_host_port(local)
    process_text = parts[6] if len(parts) > 6 else ""
    match = PROCESS_NAME.search(process_text)
    process = match.group(1) if match else ""
    classification, reason = classify_listener(protocol, host, port, process)
    return {
        "protocol": protocol,
        "local_host": host,
        "local_port": port,
        "exposure": exposure_for(host),
        "process": process or None,
        "classification": classification,
        "reason": reason,
    }


def listeners() -> dict:
    result = run_fixed(("ss", "-H", "-lntup"), timeout=20)
    if result["status"] != "ok":
        return {
            "available": result["available"],
            "status": result["status"],
            "error": result["stderr"] or "listener inventory unavailable",
            "listeners": [],
            "counts": {},
        }
    rows = []
    for line in result["stdout"].splitlines():
        row = parse_ss_line(line)
        if row is not None:
            rows.append(row)
        if len(rows) >= MAX_LISTENERS:
            break
    counts = Counter(row["classification"] for row in rows)
    return {
        "available": True,
        "status": "ok",
        "listeners": rows,
        "counts": dict(sorted(counts.items())),
        "truncated": len(result["stdout"].splitlines()) > len(rows),
    }


def component(profile: str) -> dict:
    checks = []
    for name, argv in PROFILES[profile]:
        result = run_fixed(argv)
        checks.append({"name": name, "argv_id": f"{profile}.{name}", **result})
    if checks and all(check["status"] == "ok" for check in checks):
        status = "ok"
    elif any(check["status"] == "ok" for check in checks):
        status = "limited"
    elif all(check["status"] == "command_unavailable" for check in checks):
        status = "unavailable"
    else:
        status = "error"
    return {
        "component": profile,
        "status": status,
        "read_only": True,
        "checks": checks,
    }


def summary() -> dict:
    socket_state = listeners()
    components = {}
    for profile, commands in PROFILES.items():
        components[profile] = {
            "command_available": all(shutil.which(argv[0], path=PATH) is not None for _, argv in commands),
            "diagnostic_action": f"{profile}.diagnostics",
        }
    return {
        "format": "wwcx-edge1-control-surfaces-summary-v1",
        "read_only": True,
        "parameters_accepted": False,
        "listener_inventory": socket_state,
        "components": components,
        "classification_contract": [
            "public-infrastructure",
            "peering",
            "private-control",
            "internal-service",
            "unknown-needs-attribution",
        ],
        "native_sessions": {
            "freepbx_admin": {"status": "closed", "backend_public_open_required": False},
            "freepbx_ucp": {"status": "closed", "backend_public_open_required": False},
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="WW.CX Edge1 Control Surfaces diagnostics")
    parser.add_argument("profile", choices=("summary", "listeners", *PROFILES.keys()))
    args = parser.parse_args()
    if args.profile == "summary":
        payload = summary()
    elif args.profile == "listeners":
        payload = listeners()
    else:
        payload = component(args.profile)
    print(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False))


if __name__ == "__main__":
    main()
