#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).parents[1]
UPDATER = ROOT / "deploy" / "security" / "wwcx-suricata-update"
SERVICE = ROOT / "deploy" / "systemd" / "wwcx-suricata-update.service"
TIMER = ROOT / "deploy" / "systemd" / "wwcx-suricata-update.timer"
REPAIR = ROOT / "deploy" / "repair-edge1-suricata-update-runtime.sh"

updater = UPDATER.read_text(encoding="utf-8")
service = SERVICE.read_text(encoding="utf-8")
timer = TIMER.read_text(encoding="utf-8")
repair = REPAIR.read_text(encoding="utf-8")

required_updater = (
    'SURICATA_SERVICE="${WWCX_SURICATA_SERVICE:-wwcx-network-sensor-suricata.service}"',
    'SENSOR_ENV="${WWCX_SURICATA_SENSOR_ENV:-/etc/default/wwcx-network-sensor}"',
    'RELOAD_STABILIZE_SECONDS="${WWCX_SURICATA_RELOAD_STABILIZE_SECONDS:-300}"',
    'if [ "$SURICATA_SERVICE" = "suricata.service" ]',
    'systemctl is-active --quiet "$SURICATA_SERVICE"',
    'source "$SENSOR_ENV"',
    'suricata-update --force --no-test --no-reload --fail --output "$STAGE_DIR"',
    'suricata -T -c "$SURICATA_CONFIG" -S "$CANDIDATE" "${CAPTURE_ARGS[@]}"',
    'systemctl reload "$SURICATA_SERVICE"',
    'WWCX_SURICATA_UPDATE_VALIDATE_ONLY',
    'PID_BEFORE="$(systemctl show "$SURICATA_SERVICE" --property=MainPID --value)"',
    'RESTARTS_BEFORE="$(systemctl show "$SURICATA_SERVICE" --property=NRestarts --value)"',
    'Observing managed Suricata stability for ${RELOAD_STABILIZE_SECONDS}s',
    'restore_previous_rules',
    'RELOAD_RESULT="stable-${RELOAD_STABILIZE_SECONDS}s"',
)
missing = [marker for marker in required_updater if marker not in updater]
if missing:
    raise SystemExit(f"managed updater markers missing: {missing}")

forbidden_updater = (
    "suricatasc -c reload-rules",
    "systemctl show suricata --property=MainPID",
    "systemctl show suricata --property=NRestarts",
    "--af-packet=wg0",
    "systemctl restart",
    "systemctl stop",
    "systemctl start",
    "sleep 2",
)
present = [marker for marker in forbidden_updater if marker in updater]
if present:
    raise SystemExit(f"managed updater retains forbidden legacy/runtime-control markers: {present}")

required_service = (
    "Requires=wwcx-network-sensor-suricata.service",
    "After=network-online.target wwcx-network-sensor-suricata.service",
    "ExecStart=/usr/local/sbin/wwcx-suricata-update",
    "TimeoutStartSec=15min",
)
missing = [marker for marker in required_service if marker not in service]
if missing:
    raise SystemExit(f"managed update service markers missing: {missing}")
if "Requires=suricata.service" in service:
    raise SystemExit("update service still requires legacy suricata.service")
if "ExecStartPost=" in service:
    raise SystemExit("base update service must preserve the live retention drop-in instead of duplicating ExecStartPost")

required_timer = (
    "OnCalendar=*-*-* 04:20:00 UTC",
    "RandomizedDelaySec=30m",
    "Persistent=true",
    "Unit=wwcx-suricata-update.service",
)
missing = [marker for marker in required_timer if marker not in timer]
if missing:
    raise SystemExit(f"managed update timer markers missing: {missing}")

required_repair = (
    "set -Eeuo pipefail",
    'EXPECTED_COMMIT="${EXPECTED_COMMIT:-}"',
    'LEGACY_SERVICE="suricata.service"',
    'SENSOR_SERVICE="wwcx-network-sensor-suricata.service"',
    'UPDATER_LIVE="/usr/local/sbin/wwcx-suricata-update"',
    'SERVICE_LIVE="/etc/systemd/system/wwcx-suricata-update.service"',
    'TIMER_LIVE="/etc/systemd/system/wwcx-suricata-update.timer"',
    'RETENTION_DROPIN="/etc/systemd/system/wwcx-suricata-update.service.d/retention.conf"',
    "restore_runtime_files",
    "restore_legacy_state",
    'SOURCE_BRANCH="$(git -C "$ROOT" branch --show-current)"',
    'exact detached EXPECTED_COMMIT worktree',
    '$UPDATE_TIMER must already be active; repair will not trigger a dormant persistent timer',
    'systemctl disable --now "$LEGACY_SERVICE"',
    'systemctl is-active --quiet "$SENSOR_SERVICE"',
    'systemctl is-active --quiet "$UPDATE_TIMER"',
    "expected exactly one Suricata runtime process",
    "pgrep -u suricata -f '^/usr/bin/suricata '",
    "retention ExecStartPost is missing or duplicated",
    "--pcap=",
    "memory-before.txt",
    "memory-after.txt",
    "rolled_back=true",
    "update_timer_state_preserved=true",
    "retention_dropin_preserved=true",
    "updater_targets_managed_sensor=true",
)
missing = [marker for marker in required_repair if marker not in repair]
if missing:
    raise SystemExit(f"repair transaction markers missing: {missing}")

forbidden_repair = (
    "iptables",
    "nft flush",
    "ip route add",
    "ip route del",
    "wg set",
    'systemctl restart "$SENSOR_SERVICE"',
    'systemctl stop "$SENSOR_SERVICE"',
    'systemctl start "$UPDATE_TIMER"',
    'systemctl enable "$UPDATE_TIMER"',
    "systemctl mask",
)
present = [marker for marker in forbidden_repair if marker in repair]
if present:
    raise SystemExit(f"repair transaction contains forbidden/nonessential mutations: {present}")

print("Suricata managed updater runtime repair validation passed")
