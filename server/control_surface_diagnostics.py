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
WILDCARD_HOSTS = frozenset({"0.0.0.0", "::", "*", ""})

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


def normalize_host(host: str) -> str:
    return host.split("%", 1)[0].strip("[]")


def is_loopback(host: str) -> bool:
    normalized = normalize_host(host)
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def exposure_for(host: str) -> str:
    normalized = normalize_host(host)
    if is_loopback(normalized):
        return "loopback"
    if normalized in WILDCARD_HOSTS:
        return "wildcard"
    return "specific"


def evidence_backed_listener(protocol: str, host: str, port: int | None) -> tuple[str, str] | None:
    """Return only listener attributions already proven by retained Edge1 evidence.

    These rules intentionally apply only as a fallback when ``ss -p`` cannot
    disclose a process name to the Operations API account. A visible process
    that does not match the normal process-based rules remains unknown rather
    than being overridden by a port-only assumption.
    """
    normalized = normalize_host(host)

    if normalized == "10.77.0.1" and protocol in {"tcp", "udp"} and port == 53:
        return "internal-service", "evidence-attributed WireGuard-private DNS service"
    if normalized in WILDCARD_HOSTS and protocol == "udp" and port == 123:
        return "public-infrastructure", "evidence-attributed Chrony NTP service"
    if normalized in WILDCARD_HOSTS and protocol == "udp" and port == 51820:
        return "private-control", "evidence-attributed WireGuard transport"
    if normalized in WILDCARD_HOSTS and protocol == "udp" and port == 41641:
        return "private-control", "evidence-attributed Tailscale transport"
    if normalized in {"10.77.0.1", "89.147.109.253"} and protocol in {"tcp", "udp"} and port == 5060:
        return "peering", "evidence-attributed Kamailio SIP signaling"
    if normalized in WILDCARD_HOSTS and protocol == "tcp" and port == 4460:
        return "public-infrastructure", "evidence-attributed Chrony NTS-KE service"
    if normalized in WILDCARD_HOSTS and protocol == "tcp" and port in {8001, 8003}:
        return "private-control", "evidence-attributed FreePBX UCP Node/PM2 listener"
    if normalized in WILDCARD_HOSTS and protocol == "tcp" and port in {80, 443}:
        return "public-infrastructure", "evidence-attributed Apache HTTP/HTTPS front door"
    return None


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
    if not proc:
        attributed = evidence_backed_listener(protocol, host, port)
        if attributed is not None:
            return attributed
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


def passive_socket_rows() -> tuple[dict, list[dict]]:
    result = run_fixed(("ss", "-H", "-lntu"), timeout=10)
    if result["status"] != "ok":
        return result, []
    rows = []
    for line in result["stdout"].splitlines():
        row = parse_ss_line(line)
        if row is not None:
            rows.append(row)
    return result, rows


def process_probe(name: str) -> dict:
    result = run_fixed(("pgrep", "-x", name), timeout=5)
    return {
        "name": "process_running",
        "argv_id": f"passive.{name}.process",
        "available": result["available"],
        "status": result["status"],
        "exit_code": result["exit_code"],
        "duration_ms": result["duration_ms"],
        "stdout": "running\n" if result["status"] == "ok" else "",
        "stderr": result["stderr"],
    }


def passive_asterisk() -> dict:
    process = process_probe("asterisk")
    socket_result, rows = passive_socket_rows()
    sip_loopback = any(row["local_port"] == 5061 and is_loopback(row["local_host"]) for row in rows)
    http_loopback = sorted(
        port for port in (8088, 8089)
        if any(row["local_port"] == port and is_loopback(row["local_host"]) for row in rows)
    )
    socket_ok = socket_result["status"] == "ok" and sip_loopback
    return {
        "status": "ok" if process["status"] == "ok" and socket_ok else "failed",
        "evidence": "passive process/listener probe; native Asterisk CLI remains privilege-gated",
        "checks": [
            process,
            {
                "name": "loopback_sip_listener",
                "argv_id": "passive.asterisk.listeners",
                "available": socket_result["available"],
                "status": "ok" if socket_ok else "failed",
                "exit_code": socket_result["exit_code"],
                "duration_ms": socket_result["duration_ms"],
                "stdout": json.dumps({"loopback_5061": sip_loopback, "loopback_http_ports": http_loopback}, sort_keys=True),
                "stderr": socket_result["stderr"],
            },
        ],
    }


def passive_kamailio() -> dict:
    process = process_probe("kamailio")
    socket_result, rows = passive_socket_rows()
    loopback_5060 = any(row["local_port"] == 5060 and is_loopback(row["local_host"]) for row in rows)
    non_loopback_5060 = any(row["local_port"] == 5060 and not is_loopback(row["local_host"]) for row in rows)
    socket_ok = socket_result["status"] == "ok" and loopback_5060 and non_loopback_5060
    return {
        "status": "ok" if process["status"] == "ok" and socket_ok else "failed",
        "evidence": "passive process/listener probe; native Kamailio control socket remains privilege-gated",
        "checks": [
            process,
            {
                "name": "sip_listener_pair",
                "argv_id": "passive.kamailio.listeners",
                "available": socket_result["available"],
                "status": "ok" if socket_ok else "failed",
                "exit_code": socket_result["exit_code"],
                "duration_ms": socket_result["duration_ms"],
                "stdout": json.dumps({"loopback_5060": loopback_5060, "non_loopback_5060": non_loopback_5060}, sort_keys=True),
                "stderr": socket_result["stderr"],
            },
        ],
    }


def local_https_code(path: str) -> dict:
    result = run_fixed((
        "curl",
        "-k",
        "-sS",
        "-o",
        "/dev/null",
        "-w",
        "%{http_code}",
        "--max-time",
        "5",
        "--resolve",
        "edge1.ww.cx:443:127.0.0.1",
        f"https://edge1.ww.cx{path}",
    ), timeout=8)
    code = result["stdout"].strip() if result["status"] == "ok" else ""
    accepted = code in {"200", "301", "302", "303", "307", "308"}
    return {
        "name": "private_http_surface",
        "argv_id": f"passive.freepbx.{path.strip('/').replace('/', '_') or 'root'}",
        "available": result["available"],
        "status": "ok" if result["status"] == "ok" and accepted else "failed",
        "exit_code": result["exit_code"],
        "duration_ms": result["duration_ms"],
        "stdout": code + ("\n" if code else ""),
        "stderr": result["stderr"],
    }


def passive_freepbx() -> dict:
    admin = local_https_code("/admin/")
    ucp = local_https_code("/ucp/")
    return {
        "status": "ok" if admin["status"] == "ok" and ucp["status"] == "ok" else "failed",
        "evidence": "private loopback HTTP probe; fwconsole remains unavailable to the Operations API account",
        "checks": [admin, ucp],
    }


PASSIVE_FALLBACKS = {
    "asterisk": passive_asterisk,
    "kamailio": passive_kamailio,
    "freepbx": passive_freepbx,
}


def component(profile: str) -> dict:
    checks = []
    for name, argv in PROFILES[profile]:
        result = run_fixed(argv)
        checks.append({"name": name, "argv_id": f"{profile}.{name}", **result})
    if checks and all(check["status"] == "ok" for check in checks):
        native_status = "ok"
    elif any(check["status"] == "ok" for check in checks):
        native_status = "limited"
    elif all(check["status"] == "command_unavailable" for check in checks):
        native_status = "unavailable"
    else:
        native_status = "error"

    fallback = None
    status = native_status
    if native_status in {"error", "unavailable"}:
        fallback = PASSIVE_FALLBACKS[profile]()
        if fallback["status"] == "ok":
            status = "limited"

    return {
        "component": profile,
        "status": status,
        "native_cli_status": native_status,
        "read_only": True,
        "checks": checks,
        "passive_fallback": fallback,
    }


def summary() -> dict:
    socket_state = listeners()
    components = {}
    for profile, commands in PROFILES.items():
        components[profile] = {
            "command_available": all(shutil.which(argv[0], path=PATH) is not None for _, argv in commands),
            "passive_fallback_available": True,
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
