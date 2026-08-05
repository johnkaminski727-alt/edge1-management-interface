#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "deploy" / "consolidate-edge1-suricata-runtime.sh"
COLLECTOR = ROOT / "server" / "bigbird_ops_collect.py"
script = SCRIPT.read_text(encoding="utf-8")
collector = COLLECTOR.read_text(encoding="utf-8")

required_script = (
    "set -Eeuo pipefail",
    'LEGACY_SERVICE="suricata.service"',
    'SENSOR_SERVICE="wwcx-network-sensor-suricata.service"',
    "EXPECTED_COMMIT is required",
    "network-sensor-capture-acceptance.json",
    'systemctl disable --now "$LEGACY_SERVICE"',
    "expected exactly one Suricata main process",
    "--pcap=",
    "restore_legacy_state",
    "restore_collector",
    "traffic_controls_changed=false",
)
missing = [marker for marker in required_script if marker not in script]
if missing:
    raise SystemExit(f"runtime consolidation markers missing: {missing}")

forbidden_script = (
    "iptables",
    "nft flush",
    "ip route add",
    "ip route del",
    "wg set",
    "rm -rf",
    "systemctl mask",
)
present = [marker for marker in forbidden_script if marker in script]
if present:
    raise SystemExit(f"runtime consolidation contains forbidden mutations: {present}")

required_collector = (
    "wwcx-network-sensor-suricata.service",
    "/var/log/wwcx-network-sensor/suricata/eve.json",
    "edge1-suricata-sensor-consolidation-r1",
    "'service': SURICATA_SERVICE",
    "'source_path': str(eve)",
    "'source_release': SURICATA_SOURCE_RELEASE",
)
missing = [marker for marker in required_collector if marker not in collector]
if missing:
    raise SystemExit(f"collector consolidation markers missing: {missing}")

forbidden_collector = (
    "EVE = Path('/var/log/suricata/eve.json')",
    "'suricata.service', 'ssh.service'",
)
present = [marker for marker in forbidden_collector if marker in collector]
if present:
    raise SystemExit(f"collector still contains legacy source markers: {present}")

print("Suricata runtime consolidation validation passed")
