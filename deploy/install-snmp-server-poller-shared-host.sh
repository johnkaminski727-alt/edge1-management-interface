#!/bin/sh
set -eu

REPO_ROOT=${1:-$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)}
DEST=${WWCX_SNMP_SERVER_POLLER_ROOT:-$HOME/wwcx-snmp-server-poller}
PRIVATE_DIR=${WWCX_SNMP_SERVER_POLLER_PRIVATE:-$HOME/private/wwcx-snmp-server-poller}
OUTPUT=${WWCX_SNMP_SERVER_POLLER_OUTPUT:-$PRIVATE_DIR/measurements.jsonl}
PYTHON_BIN=${WWCX_SNMP_SERVER_POLLER_PYTHON:-python3}
POLLER_ID=${WWCX_SNMP_SERVER_POLLER_ID:-business159-shared-host}
DISPLAY_NAME=${WWCX_SNMP_SERVER_POLLER_DISPLAY_NAME:-WW.CX Shared Host}
OBSERVER_HOST=${WWCX_SNMP_SERVER_POLLER_HOST:-business159.web-hosting.com}
DISK_PATH=${WWCX_SNMP_SERVER_POLLER_DISK_PATH:-$HOME}

for command_name in "$PYTHON_BIN" install grep tail; do
    command -v "$command_name" >/dev/null 2>&1 || {
        echo "Missing required command: $command_name" >&2
        exit 1
    }
done

"$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 6):
    raise SystemExit("WW.CX SNMP server poller requires Python 3.6 or newer")
PY

umask 077
mkdir -p "$DEST" "$PRIVATE_DIR"
install -m 0700 "$REPO_ROOT/server/edge1_snmp_server_pollers.py" "$DEST/server_poller.py"

"$PYTHON_BIN" "$DEST/server_poller.py" collect \
    --poller-id "$POLLER_ID" \
    --display-name "$DISPLAY_NAME" \
    --observer-host "$OBSERVER_HOST" \
    --disk-path "$DISK_PATH" \
    --output "$OUTPUT" \
    --max-records 10000 >/dev/null

CRON_LINE="*/5 * * * * $PYTHON_BIN $DEST/server_poller.py collect --poller-id $POLLER_ID --display-name '$DISPLAY_NAME' --observer-host $OBSERVER_HOST --disk-path $DISK_PATH --output $OUTPUT --max-records 10000 >/dev/null 2>&1"
if [ "${WWCX_SNMP_SERVER_POLLER_INSTALL_CRON:-1}" = "1" ]; then
    command -v crontab >/dev/null 2>&1 || {
        echo "crontab is required unless WWCX_SNMP_SERVER_POLLER_INSTALL_CRON=0" >&2
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

WWCX_SNMP_SERVER_POLLER_OUTPUT="$OUTPUT" \
WWCX_SNMP_SERVER_POLLER_ID="$POLLER_ID" \
WWCX_SNMP_SERVER_POLLER_PYTHON="$PYTHON_BIN" \
"$REPO_ROOT/deploy/snmp-server-poller-shared-host-smoke-test.sh"

echo "Shared-host SNMP server poller installed and verified."
echo "Private measurements: $OUTPUT"
echo "No network listener or SNMP daemon was enabled."
