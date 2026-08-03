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

suricata_unit = (ROOT / "deploy/systemd/wwcx-network-sensor-suricata.service").read_text(encoding="utf-8")
for marker in (
    "ExecStartPre=+/usr/bin/install -d -o root -g root -m 0755 /var/log/wwcx-network-sensor",
    "ExecStartPre=+/usr/bin/install -d -o suricata -g root -m 2770 /var/log/wwcx-network-sensor/suricata",
    "ExecStartPre=+/usr/bin/install -d -o wwsensor -g root -m 2770 /var/log/wwcx-network-sensor/zeek",
    "--user=suricata",
    "--group=suricata",
    "ReadWritePaths=/var/log/wwcx-network-sensor /run/wwcx-network-sensor",
    "CapabilityBoundingSet=CAP_CHOWN CAP_SETGID CAP_SETUID CAP_SETPCAP CAP_NET_ADMIN CAP_NET_RAW CAP_SYS_NICE",
    "UMask=0007",
):
    assert marker in suricata_unit, marker
assert "AmbientCapabilities=" not in suricata_unit
assert "User=suricata" not in suricata_unit
assert "Group=suricata" not in suricata_unit

pcap_unit = (ROOT / "deploy/systemd/wwcx-network-sensor-pcap.service").read_text(encoding="utf-8")
for marker in (
    "User=root",
    "Group=root",
    "ExecStartPre=+/usr/bin/install -d -o root -g root -m 0755 /var/lib/wwcx-network-sensor",
    "ExecStartPre=+/usr/bin/install -d -o wwsensor -g root -m 2770 /var/lib/wwcx-network-sensor/pcap",
    "ExecStartPre=+/usr/bin/install -d -o wwsensor -g root -m 2770 /var/lib/wwcx-network-sensor/extracted",
    "ReadWritePaths=/var/lib/wwcx-network-sensor",
    "CapabilityBoundingSet=CAP_CHOWN CAP_SETGID CAP_SETUID CAP_NET_ADMIN CAP_NET_RAW",
    "UMask=0007",
):
    assert marker in pcap_unit, marker
assert "AmbientCapabilities=" not in pcap_unit

pcap_wrapper = (ROOT / "tools/networking/network-sensor-pcap.sh").read_text(encoding="utf-8")
assert "-Z wwsensor" in pcap_wrapper
assert "/usr/bin/tcpdump" in pcap_wrapper

zeek_unit = (ROOT / "deploy/systemd/wwcx-network-sensor-zeek.service").read_text(encoding="utf-8")
for marker in (
    "ExecStartPre=+/usr/bin/install -d -o wwsensor -g root -m 2770 /var/log/wwcx-network-sensor/zeek",
    "ExecStartPre=+/usr/bin/install -d -o wwsensor -g root -m 2770 /var/lib/wwcx-network-sensor/extracted",
    "ReadWritePaths=/var/log/wwcx-network-sensor /var/lib/wwcx-network-sensor",
    "UMask=0007",
):
    assert marker in zeek_unit, marker

installer = (ROOT / "deploy/install-edge1-network-sensor.sh").read_text(encoding="utf-8")
for marker in (
    'MISSING_PACKAGES=""',
    "for package in suricata tcpdump jq ethtool",
    'command -v "$package"',
    'apt-cache policy "$package"',
    "APT installation skipped",
):
    assert marker in installer, marker
assert "apt-get install -y suricata tcpdump jq python3 ethtool" not in installer

# Run the exact operator-facing validation path used by the guarded live installer.
# Its forbidden-command scan is intentionally limited to executable and installed
# network-sensor runtime assets, rather than tests and documentation containing
# literal negative-test strings.
subprocess.run([
    "bash",
    str(ROOT / "tools/networking/validate-edge1-network-sensor.sh"),
], check=True)

print("Edge1 passive network sensor repository validation passed.")
