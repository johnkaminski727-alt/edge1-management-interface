#!/usr/bin/python3
"""Publish read-only Network Defense using current Edge1 observations."""

import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path("/opt/edge1-management-interface")
WEB = Path("/var/www/edge1-status")
DEST = WEB / "network-defense/data/network-defense.json"

def load(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Expected JSON object")
    return data

def source_state(data, schema):
    if data.get("schema_version") != schema:
        raise ValueError("Unexpected observation schema")
    if data.get("read_only") is not True:
        raise ValueError("Read-only contract missing")
    if data.get("traffic_controls_changed") is not False:
        raise ValueError("Safety contract missing")

    stamp = dt.datetime.fromisoformat(
        data["generated_at"].replace("Z", "+00:00")
    )
    age = (
        dt.datetime.now(dt.timezone.utc) - stamp
    ).total_seconds()

    return 0 <= age <= 300, max(0, int(age))

def component(name, observed, healthy, detail):
    return {
        "name": name,
        "state": (
            "healthy" if observed and healthy
            else "attention" if observed
            else "unavailable"
        ),
        "observed": observed,
        "enforcement_verified": False,
        "detail": detail,
        "metrics": {},
    }

def main():
    # Run the existing exporter privately. Missing historical inputs
    # must remain unavailable; do not fabricate replacements.
    with tempfile.TemporaryDirectory(
        prefix="edge1-network-defense-"
    ) as folder:
        original = Path(folder) / "legacy.json"

        result = subprocess.run(
            [
                "/usr/bin/python3",
                str(ROOT / "server/network_defense_sensor_exporter.py"),
                "--output", str(original),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=75,
        )

        if result.returncode:
            raise RuntimeError(
                "Original exporter failed: " +
                result.stderr[-400:]
            )

        data = load(original)

    core = load(WEB / "core-status.json")
    crowd = load(WEB / "crowdsec-status.json")

    core_ok, core_age = source_state(
        core, "wwcx.core-observation.v1"
    )
    crowd_ok, crowd_age = source_state(
        crowd, "wwcx.crowdsec-observation.v1"
    )

    if data.get("traffic_controls_changed") is not False:
        raise ValueError("Original safety contract failed")

    components = data.setdefault("components", {})
    sources = data.setdefault("sources", {})

    services = core.get("services", {})
    active = sum(
        value.get("state") == "active"
        for value in services.values()
    )

    components["core_services"] = component(
        "Core system services",
        core_ok,
        bool(services) and active == len(services),
        (
            f"{active}/{len(services)} monitored services active"
            if core_ok else
            "Core observation stale or unavailable"
        ),
    )

    dns_active = all(
        services.get(name, {}).get("state") == "active"
        for name in ("AdGuardHome", "unbound")
    )

    components["dns"] = component(
        "DNS service availability",
        core_ok,
        dns_active,
        (
            "AdGuard Home and Unbound service states observed; "
            "DNS query success is not independently verified."
            if core_ok else
            "Current DNS service observation unavailable."
        ),
    )

    for key, label, item in (
        (
            "crowdsec_ipv4",
            "CrowdSec IPv4 INPUT",
            crowd.get("input", {}).get("ipv4", {}),
        ),
        (
            "crowdsec_ipv6",
            "CrowdSec IPv6 INPUT",
            crowd.get("input", {}).get("ipv6", {}),
        ),
        (
            "crowdsec_vpn",
            "CrowdSec IPv4 VPN forwarding",
            crowd.get("forward", {}).get("ipv4", {}),
        ),
    ):
        components[key] = component(
            label,
            crowd_ok,
            item.get("verified") is True,
            (
                "Expected firewall hook observed; "
                "not a new end-to-end packet test."
                if crowd_ok else
                "CrowdSec observation stale or unavailable."
            ),
        )

    for name, path, current, age in (
        ("core_live", "core-status.json", core_ok, core_age),
        (
            "crowdsec_live",
            "crowdsec-status.json",
            crowd_ok,
            crowd_age,
        ),
    ):
        sources[name] = {
            "available": current,
            "required": True,
            "file": path,
            "age_seconds": age,
            "stale_after_seconds": 300,
            "stale": not current,
            "detail": (
                "Current read-only observation"
                if current else
                "Observation stale or invalid"
            ),
        }

    summary = data.setdefault("summary", {})
    summary["component_count"] = len(components)
    summary["observed_component_count"] = sum(
        item.get("observed") is True
        for item in components.values()
    )
    summary["verified_enforcement_count"] = sum(
        item.get("enforcement_verified") is True
        for item in components.values()
    )
    summary["source_count"] = len(sources)
    summary["available_source_count"] = sum(
        item.get("available") is True
        for item in sources.values()
    )
    summary["stale_sources"] = [
        key for key, value in sources.items()
        if value.get("stale") is True
    ]

    data["generated_at"] = dt.datetime.now(
        dt.timezone.utc
    ).isoformat()
    data["overall_state"] = (
        "limited" if core_ok and crowd_ok else "stale"
    )
    data["traffic_controls_changed"] = False

    limitations = data.setdefault("limitations", [])
    limitations.append(
        "Firewall hooks and service states are observations, "
        "not proof of end-to-end security enforcement."
    )

    DEST.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix=".network-defense-",
        dir=str(DEST.parent),
    )

    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(data, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, DEST)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

    print(
        "Live sources:",
        int(core_ok) + int(crowd_ok), "/ 2"
    )
    print(
        "Observed components:",
        summary["observed_component_count"],
        "/", summary["component_count"],
    )
    print("Overall state:", data["overall_state"])

if __name__ == "__main__":
    main()
