#!/bin/sh
set -eu

DEST=${WWCX_TIME_AUTHORITY_ROOT:-$HOME/wwcx-time-authority}
OUTPUT=${WWCX_TIME_AUTHORITY_OUTPUT:-$HOME/private/wwcx-time-authority/measurements.jsonl}
PYTHON_BIN=${WWCX_TIME_AUTHORITY_PYTHON:-python3}
CRON_LINE="*/15 * * * * WWCX_TIME_AUTHORITY_PYTHON=$PYTHON_BIN $DEST/collect-shared-host.sh >/dev/null 2>&1"

test -x "$DEST/ntp_rtt_probe.py"
test -x "$DEST/collect-shared-host.sh"
test -r "$DEST/sources.json"
test -s "$OUTPUT"

tail -n 5 "$OUTPUT" | "$PYTHON_BIN" -c '
import json, sys
records = [json.loads(line) for line in sys.stdin if line.strip()]
assert records
assert all(item.get("observer_id") == "shared-host" for item in records)
assert any(item.get("reachable") for item in records)
'

if [ "${WWCX_TIME_AUTHORITY_INSTALL_CRON:-1}" = "1" ]; then
    crontab -l 2>/dev/null | grep -Fqx "$CRON_LINE"
fi

echo "WW.CX Time Authority shared-host smoke test passed."
