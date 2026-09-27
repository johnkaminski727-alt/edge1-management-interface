#!/usr/bin/python3
import datetime
import json
import os
import subprocess
import tempfile
from pathlib import Path

OUTPUT = Path("/var/www/edge1-status/core-status.json")

SERVICES = (
    "ufw",
    "wg-quick@wg0",
    "wireguard-nat",
    "crowdsec",
    "crowdsec-firewall-bouncer",
    "edge1-crowdsec-bootstrap",
    "edge1-crowdsec-enforce",
    "edge1-crowdsec-forward",
    "AdGuardHome",
    "unbound",
    "edge1-operations-api",
)

def run(*args):
    try:
        result = subprocess.run(
            args, capture_output=True, text=True,
            check=False, timeout=10
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None

def service(name):
    state = run("systemctl", "is-active", name)
    enabled = run("systemctl", "is-enabled", name)
    return {
        "state": state if state in (
            "active", "inactive", "failed", "activating"
        ) else "unknown",
        "enabled": enabled == "enabled"
            if enabled is not None else None,
    }

def interface(name):
    try:
        data = json.loads(
            run("ip", "-j", "link", "show", "dev", name)
            or "[]"
        )
        if len(data) != 1:
            return {"available": False, "up": None}
        flags = data[0].get("flags", [])
        return {
            "available": True,
            "up": "UP" in flags,
        }
    except (ValueError, TypeError):
        return {"available": False, "up": None}

def kernel_setting(path):
    try:
        return int(Path(path).read_text().strip())
    except (OSError, ValueError):
        return None

def main():
    services = {name: service(name) for name in SERVICES}

    snapshot = {
        "schema_version": "wwcx.core-observation.v1",
        "generated_at": datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat(),
        "read_only": True,
        "traffic_controls_changed": False,
        "services": services,
        "interfaces": {
            name: interface(name)
            for name in ("ens3", "wg0")
        },
        "routing": {
            "ipv4_forwarding": kernel_setting(
                "/proc/sys/net/ipv4/ip_forward"
            ),
            "ipv6_forwarding": kernel_setting(
                "/proc/sys/net/ipv6/conf/all/forwarding"
            ),
        },
        "limits": [
            "Service availability does not prove end-to-end DNS",
            "Interface UP does not prove external connectivity",
            "No peer identities, IP addresses or raw routes included",
        ],
    }

    descriptor, temporary = tempfile.mkstemp(
        prefix=".core-status-",
        dir=str(OUTPUT.parent)
    )
    try:
        with os.fdopen(descriptor, "w") as handle:
            json.dump(snapshot, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, OUTPUT)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

    print(
        "Active services:",
        sum(x["state"] == "active"
            for x in services.values()),
        "/", len(services)
    )
    print("WireGuard interface UP:",
          snapshot["interfaces"]["wg0"]["up"])
    print("IPv4 forwarding:",
          snapshot["routing"]["ipv4_forwarding"])

if __name__ == "__main__":
    main()
