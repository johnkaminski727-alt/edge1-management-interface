#!/usr/bin/env python3
"""Repository validation entrypoint for the Edge1 passive network sensor."""

from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
REQUIRED = (
    "server/network_sensor_exporter.py",
    "tests/test_network_sensor_exporter.py",
    "deploy/install-edge1-network-sensor.sh",
    "tools/networking/discover-edge1-network-sensor.sh",
    "tools/networking/validate-edge1-network-sensor.sh",
    "src/web/network-sensor/index.html",
    "docs/security/edge1-network-sensor.md",
)

for relative in REQUIRED:
    assert (ROOT / relative).is_file(), relative

subprocess.run(["python3", "-m", "py_compile", str(ROOT / "server/network_sensor_exporter.py")], check=True)
for path in (
    ROOT / "deploy/install-edge1-network-sensor.sh",
    ROOT / "tools/networking/discover-edge1-network-sensor.sh",
    ROOT / "tools/networking/network-sensor-pcap.sh",
    ROOT / "tools/networking/network-sensor-prune.sh",
    ROOT / "tools/networking/network-sensor-zeek.sh",
    ROOT / "tools/networking/validate-edge1-network-sensor.sh",
):
    subprocess.run(["bash", "-n", str(path)], check=True)

spec = importlib.util.spec_from_file_location("network_sensor_tests", ROOT / "tests/test_network_sensor_exporter.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)
result = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromModule(module))
assert result.wasSuccessful()

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

print("Edge1 passive network sensor repository validation passed.")
