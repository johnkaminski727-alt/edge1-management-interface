#!/bin/sh
set -eu

REPO_ROOT=${EDGE1_MANAGEMENT_ROOT:-/opt/edge1-management-interface}
SYSTEMCTL_BIN=${EDGE1_TIME_AUTHORITY_SYSTEMCTL:-systemctl}

for command_name in python3 "$SYSTEMCTL_BIN" curl install useradd; do
    command -v "$command_name" >/dev/null 2>&1 || {
        echo "Missing required command: $command_name" >&2
        exit 1
    }
done

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

echo "WW.CX Time Authority Edge1 preflight passed."
