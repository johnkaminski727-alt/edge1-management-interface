#!/bin/sh
set -eu

REPO_ROOT=${EDGE1_MANAGEMENT_ROOT:-/opt/edge1-management-interface}
SYSTEMCTL_BIN=${EDGE1_TIME_AUTHORITY_SYSTEMCTL:-systemctl}
SIMULATION=${EDGE1_TIME_AUTHORITY_SIMULATION:-0}
DASHBOARD_PORT=${EDGE1_TIME_AUTHORITY_DASHBOARD_PORT:-8101}
UNIT_DIR=${EDGE1_TIME_AUTHORITY_UNIT_DIR:-/etc/systemd/system}

for command_name in python3 "$SYSTEMCTL_BIN" curl install; do
    command -v "$command_name" >/dev/null 2>&1 || {
        echo "Missing required command: $command_name" >&2
        exit 1
    }
done

if [ "$SIMULATION" != "1" ]; then
    for command_name in useradd systemd-analyze stat; do
        command -v "$command_name" >/dev/null 2>&1 || {
            echo "Missing required command: $command_name" >&2
            exit 1
        }
    done

    [ -d "$UNIT_DIR" ] || {
        echo "Systemd unit directory is missing: $UNIT_DIR" >&2
        exit 1
    }

    UNIT_DIR_OWNER=$(stat -c '%U:%G' "$UNIT_DIR" 2>/dev/null || true)
    UNIT_DIR_MODE=$(stat -c '%a' "$UNIT_DIR" 2>/dev/null || true)
    if [ "$UNIT_DIR_OWNER" != "root:root" ] || [ "$UNIT_DIR_MODE" != "755" ]; then
        echo "Refusing Time Authority rollout: systemd unit directory must remain root:root mode 755; found $UNIT_DIR_OWNER mode $UNIT_DIR_MODE at $UNIT_DIR" >&2
        exit 1
    fi
fi

python3 - <<'PY'
import sys

if sys.version_info < (3, 10):
    raise SystemExit("Edge1 Time Authority requires Python 3.10 or newer")
PY

for required_path in \
    "$REPO_ROOT/tools/time_authority/ntp_rtt_probe.py" \
    "$REPO_ROOT/tools/time_authority/collect-edge1.sh" \
    "$REPO_ROOT/server/time_authority_server.py" \
    "$REPO_ROOT/modules/time-authority/config/sources.json" \
    "$REPO_ROOT/tests/validate_time_authority.py"; do
    test -r "$required_path" || {
        echo "Missing required package file: $required_path" >&2
        exit 1
    }
done

python3 -m json.tool "$REPO_ROOT/modules/time-authority/config/sources.json" >/dev/null
python3 "$REPO_ROOT/tests/validate_time_authority.py"

if [ "$SIMULATION" != "1" ]; then
    python3 - "$DASHBOARD_PORT" <<'PY'
import json
import socket
import sys
import urllib.request

port = int(sys.argv[1])
if not 1 <= port <= 65535:
    raise SystemExit(f"Invalid Time Authority dashboard port: {port}")

probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
probe.settimeout(0.5)
try:
    in_use = probe.connect_ex(("127.0.0.1", port)) == 0
finally:
    probe.close()

if in_use:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=1.5) as response:
            payload = json.load(response)
    except Exception:
        raise SystemExit(f"Time Authority dashboard port {port} is already in use by an unidentified service")
    if payload.get("service") != "edge1-time-authority":
        owner = payload.get("service") or "an unidentified service"
        raise SystemExit(f"Time Authority dashboard port {port} is already in use by {owner}")
PY

    systemd-analyze verify \
        "$REPO_ROOT/deploy/systemd/edge1-time-authority-collector.service" \
        "$REPO_ROOT/deploy/systemd/edge1-time-authority-collector.timer" \
        "$REPO_ROOT/deploy/systemd/edge1-time-authority-dashboard.service"
fi

echo "WW.CX Time Authority Edge1 preflight passed."
