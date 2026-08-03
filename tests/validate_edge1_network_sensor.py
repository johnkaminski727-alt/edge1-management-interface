#!/usr/bin/env python3
"""Repository validation entrypoint for the Edge1 passive network sensor."""

from __future__ import annotations

import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
REQUIRED = (
    "server/network_sensor_exporter.py",
    "server/security_correlation_sensor_exporter.py",
    "server/network_defense_sensor_exporter.py",
    "tests/test_network_sensor_exporter.py",
    "tests/test_network_sensor_correlation_integration.py",
    "tests/test_network_sensor_network_defense_integration.py",
    "deploy/install-edge1-network-sensor.sh",
    "deploy/systemd/wwcx-security-correlation.service",
    "deploy/systemd/wwcx-network-defense.service",
    "tools/networking/discover-edge1-network-sensor.sh",
    "tools/networking/validate-edge1-network-sensor.sh",
    "src/web/network-sensor/index.html",
    "docs/security/edge1-network-sensor.md",
)

for relative in REQUIRED:
    assert (ROOT / relative).is_file(), relative

subprocess.run([
    "python3", "-m", "py_compile",
    str(ROOT / "server/network_sensor_exporter.py"),
    str(ROOT / "server/security_correlation_sensor_exporter.py"),
    str(ROOT / "server/network_defense_sensor_exporter.py"),
], check=True)
for test in (
    ROOT / "tests/test_network_sensor_exporter.py",
    ROOT / "tests/test_network_sensor_correlation_integration.py",
    ROOT / "tests/test_network_sensor_network_defense_integration.py",
):
    subprocess.run(["python3", str(test)], check=True)

for path in (
    ROOT / "deploy/install-edge1-network-sensor.sh",
    ROOT / "tools/networking/discover-edge1-network-sensor.sh",
    ROOT / "tools/networking/network-sensor-pcap.sh",
    ROOT / "tools/networking/network-sensor-prune.sh",
    ROOT / "tools/networking/network-sensor-zeek.sh",
    ROOT / "tools/networking/validate-edge1-network-sensor.sh",
):
    subprocess.run(["bash", "-n", str(path)], check=True)
    subprocess.run(["sh", "-n", str(path)], check=True)

correlation_unit = (ROOT / "deploy/systemd/wwcx-security-correlation.service").read_text(encoding="utf-8")
assert "security_correlation_sensor_exporter.py" in correlation_unit
assert "ReadOnlyPaths=-/var/lib/wwcx-network-sensor/restricted" in correlation_unit
network_defense_unit = (ROOT / "deploy/systemd/wwcx-network-defense.service").read_text(encoding="utf-8")
assert "network_defense_sensor_exporter.py" in network_defense_unit

combined = "\n".join(
    path.read_text(encoding="utf-8", errors="replace")
    for path in ROOT.rglob("*network-sensor*")
    if path.is_file() and path.name not in {"validate_edge1_network_sensor.py", "validate-edge1-network-sensor.sh"}
)
for forbidden in (
    "iptables -F",
    "nft flush ruleset",
    "ip route add default",
    "sysctl -w net.ipv4.ip_forward=1",
):
    assert forbidden not in combined, forbidden

# Run the same operator-facing validation path used by the guarded live installer.
# This prevents CI from passing while the live deployment preflight fails.
subprocess.run([
    "bash",
    str(ROOT / "tools/networking/validate-edge1-network-sensor.sh"),
], check=True)

print("Edge1 passive network sensor repository validation passed.")
