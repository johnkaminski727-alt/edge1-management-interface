#!/bin/sh
set -eu

REPO_ROOT=${1:-$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)}
DEST=${WWCX_TIME_AUTHORITY_ROOT:-$HOME/wwcx-time-authority}
PRIVATE_DIR=${WWCX_TIME_AUTHORITY_PRIVATE:-$HOME/private/wwcx-time-authority}
PYTHON_BIN=${WWCX_TIME_AUTHORITY_PYTHON:-python3}

for command_name in "$PYTHON_BIN" install grep tail; do
    command -v "$command_name" >/dev/null 2>&1 || {
        echo "Missing required command: $command_name" >&2
        exit 1
    }
done

"$PYTHON_BIN" - <<'PY'
import sys

if sys.version_info < (3, 6):
    raise SystemExit("WW.CX Time Authority requires Python 3.6 or newer")
PY

umask 077
mkdir -p "$DEST" "$PRIVATE_DIR"
install -m 0700 "$REPO_ROOT/tools/time_authority/ntp_rtt_probe.py" "$DEST/ntp_rtt_probe.py"
install -m 0700 "$REPO_ROOT/tools/time_authority/collect-shared-host.sh" "$DEST/collect-shared-host.sh"
install -m 0600 "$REPO_ROOT/modules/time-authority/config/sources.json" "$DEST/sources.json"

WWCX_TIME_AUTHORITY_PYTHON=$PYTHON_BIN "$DEST/collect-shared-host.sh" >/dev/null

CRON_LINE="*/15 * * * * WWCX_TIME_AUTHORITY_PYTHON=$PYTHON_BIN $DEST/collect-shared-host.sh >/dev/null 2>&1"
if [ "${WWCX_TIME_AUTHORITY_INSTALL_CRON:-1}" = "1" ]; then
    command -v crontab >/dev/null 2>&1 || {
        echo "crontab is required unless WWCX_TIME_AUTHORITY_INSTALL_CRON=0" >&2
        exit 1
    }
    EXISTING_CRONTAB=$(crontab -l 2>/dev/null || true)
    if ! printf '%s\n' "$EXISTING_CRONTAB" | grep -Fqx "$CRON_LINE"; then
        {
            test -z "$EXISTING_CRONTAB" || printf '%s\n' "$EXISTING_CRONTAB"
            printf '%s\n' "$CRON_LINE"
        } | crontab -
    fi
fi

WWCX_TIME_AUTHORITY_PYTHON=$PYTHON_BIN "$REPO_ROOT/deploy/time-authority-shared-host-smoke-test.sh"
echo "Shared-host Time Authority collector installed and verified."
