#!/usr/bin/env python3
"""Read-only validation of the security services actually deployed on Edge1."""
from __future__ import annotations

import json
import shutil
import socket
import ssl
import subprocess
from datetime import datetime, timezone

REQUIRED_SERVICES = (
    "nginx.service",
    "edge1-security-auth.service",
    "edge1-operations-api.service",
    "crowdsec.service",
    "crowdsec-firewall-bouncer.service",
    "fail2ban.service",
    "AdGuardHome.service",
    "ufw.service",
)
OPTIONAL_SERVICES = (
    "edge1-crowdsec-bootstrap.service",
    "edge1-crowdsec-enforce.service",
    "edge1-crowdsec-forward.service",
    "edge1-crowdsec-observation.service",
)

def run(argv: list[str], timeout: int = 8) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
        env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin"},
    )


def service_state(name: str) -> str:
    result = run(["systemctl", "is-active", name])
    value = result.stdout.strip()
    return value or "unknown"


def listener_present(protocol: str, address_port: str) -> bool:
    args = ["ss", "-H", "-ln" + protocol]
    result = run(args)
    if result.returncode != 0:
        return False
    return any(address_port in line for line in result.stdout.splitlines())


started = datetime.now(timezone.utc)
checks: list[dict[str, object]] = []

for service in REQUIRED_SERVICES:
    state = service_state(service)
    checks.append({
        "id": "service:" + service,
        "status": "pass" if state == "active" else "fail",
        "detail": state,
        "required": True,
    })

for service in OPTIONAL_SERVICES:
    state = service_state(service)
    checks.append({
        "id": "service:" + service,
        "status": "info" if state in {"active", "inactive", "failed", "unknown"} else "info",
        "detail": state,
        "required": False,
    })

wg = run(["ip", "link", "show", "wg0"])
checks.append({
    "id": "wireguard:wg0",
    "status": "pass" if wg.returncode == 0 else "fail",
    "detail": "present" if wg.returncode == 0 else "missing",
    "required": True,
})

https_ok = listener_present("t", "10.77.0.1:443")
checks.append({
    "id": "listener:https-private",
    "status": "pass" if https_ok else "fail",
    "detail": "10.77.0.1:443" if https_ok else "missing",
    "required": True,
})

dns_udp_ok = listener_present("u", "10.77.0.1:53")
dns_tcp_ok = listener_present("t", "10.77.0.1:53")
checks.append({
    "id": "listener:dns-private",
    "status": "pass" if dns_udp_ok and dns_tcp_ok else "fail",
    "detail": f"udp={dns_udp_ok} tcp={dns_tcp_ok}",
    "required": True,
})

cert_ok = False
cert_detail = "TLS probe failed"
try:
    context = ssl.create_default_context()
    with socket.create_connection(("10.77.0.1", 443), timeout=5) as raw:
        with context.wrap_socket(raw, server_hostname="edge1.ww.cx") as tls:
            cert = tls.getpeercert()
            not_after = cert.get("notAfter")
            if not_after:
                expiry = datetime.strptime(
                    not_after,
                    "%b %d %H:%M:%S %Y %Z",
                ).replace(tzinfo=timezone.utc)
                remaining = (expiry - datetime.now(timezone.utc)).total_seconds()
                cert_ok = remaining > 86400
                cert_detail = (
                    "served certificate valid >24h"
                    if cert_ok
                    else "served certificate expires within 24h"
                )
            else:
                cert_detail = "served certificate has no expiry"
except (OSError, ssl.SSLError, ValueError) as exc:
    cert_detail = "TLS probe failed: " + exc.__class__.__name__

checks.append({
    "id": "tls:edge1.ww.cx",
    "status": "pass" if cert_ok else "fail",
    "detail": cert_detail,
    "required": True,
})

suricata_present = shutil.which("suricata") is not None
checks.append({
    "id": "suricata",
    "status": "info",
    "detail": "installed" if suricata_present else "not installed; not required by this Edge1 profile",
    "required": False,
})

failed = [item["id"] for item in checks if item["required"] and item["status"] != "pass"]
result = "success" if not failed else "failed"

payload = {
    "action": "security.validate_config",
    "profile": "edge1-live-security-stack-v1",
    "started": started.isoformat(),
    "completed": datetime.now(timezone.utc).isoformat(),
    "result": result,
    "checks": checks,
    "failed_required_checks": failed,
    "configuration_changed": False,
    "services_restarted": False,
    "traffic_changed": False,
}

print(json.dumps(payload, sort_keys=True))
raise SystemExit(0 if result == "success" else 1)
