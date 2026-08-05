#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "deploy" / "consolidate-edge1-suricata-runtime.sh"
COLLECTOR = ROOT / "server" / "bigbird_ops_collect.py"
UNIT = ROOT / "deploy" / "systemd" / "wwcx-network-sensor-suricata.service"
RELOAD = ROOT / "tools" / "security" / "reload-suricata-rules.sh"
script = SCRIPT.read_text(encoding="utf-8")
collector = COLLECTOR.read_text(encoding="utf-8")
unit = UNIT.read_text(encoding="utf-8")
reload_script = RELOAD.read_text(encoding="utf-8")

required_script = (
    "set -Eeuo pipefail",
    'LEGACY_SERVICE="suricata.service"',
    'SENSOR_SERVICE="wwcx-network-sensor-suricata.service"',
    'SENSOR_UNIT_SOURCE="$ROOT/deploy/systemd/wwcx-network-sensor-suricata.service"',
    'SENSOR_UNIT_LIVE="/etc/systemd/system/wwcx-network-sensor-suricata.service"',
    'SENSOR_UNIT_BACKUP="$BACKUP_DIR/wwcx-network-sensor-suricata.service"',
    "SENSOR_UNIT_WAS_PRESENT=false",
    'SENSOR_ENABLED="$(systemctl is-enabled "$SENSOR_SERVICE" 2>/dev/null || true)"',
    'SENSOR_ACTIVE="$(systemctl is-active "$SENSOR_SERVICE" 2>/dev/null || true)"',
    "EXPECTED_COMMIT is required",
    "network-sensor-capture-acceptance.json",
    'grep -Fxq \'ExecReload=+/bin/kill -USR2 $MAINPID\' "$SENSOR_UNIT_SOURCE"',
    'cp -a "$SENSOR_UNIT_LIVE" "$SENSOR_UNIT_BACKUP"',
    'install -D -o root -g root -m 0644 "$SENSOR_UNIT_SOURCE" "$SENSOR_UNIT_LIVE"',
    'cmp -s "$SENSOR_UNIT_SOURCE" "$SENSOR_UNIT_LIVE"',
    "systemctl daemon-reload",
    'systemctl cat "$SENSOR_SERVICE"',
    'systemctl disable --now "$LEGACY_SERVICE"',
    "expected exactly one Suricata main process",
    "--pcap=",
    "capture_failure_evidence",
    "failure-service-journal.txt",
    "restore_legacy_state",
    "restore_collector",
    "restore_sensor_state",
    "managed_unit_installed=true",
    "managed_reload_contract_installed=true",
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
    'systemctl reload "$SENSOR_SERVICE"',
    "managed_reload_verified=true",
)
present = [marker for marker in forbidden_script if marker in script]
if present:
    raise SystemExit(f"runtime consolidation contains forbidden or nonessential mutations: {present}")

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

if "ExecReload=+/bin/kill -USR2 $MAINPID" not in unit:
    raise SystemExit("managed Suricata unit does not use privileged SIGUSR2 rule reload")
if "ExecReload=/bin/kill -HUP $MAINPID" in unit:
    raise SystemExit("managed Suricata unit still uses the log-reopen signal for rule reload")
if "CAP_KILL" in unit:
    raise SystemExit("managed Suricata daemon capability boundary was broadened unnecessarily")

required_reload = (
    "wwcx-network-sensor-suricata.service",
    'systemctl is-active --quiet "$SURICATA_SERVICE"',
    'systemctl reload "$SURICATA_SERVICE"',
    '"service": "$SURICATA_SERVICE"',
)
missing = [marker for marker in required_reload if marker not in reload_script]
if missing:
    raise SystemExit(f"managed Suricata reload markers missing: {missing}")
if "systemctl reload suricata.service" in reload_script:
    raise SystemExit("reload tool still targets the retired legacy service")

print("Suricata runtime consolidation validation passed")
