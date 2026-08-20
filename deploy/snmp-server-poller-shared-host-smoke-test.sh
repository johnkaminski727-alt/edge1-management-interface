#!/bin/sh
set -eu

OUTPUT=${WWCX_SNMP_SERVER_POLLER_OUTPUT:-$HOME/private/wwcx-snmp-server-poller/measurements.jsonl}
POLLER_ID=${WWCX_SNMP_SERVER_POLLER_ID:-business159-shared-host}
PYTHON_BIN=${WWCX_SNMP_SERVER_POLLER_PYTHON:-python3}

[ -s "$OUTPUT" ] || {
    echo "Missing shared-host server poller output: $OUTPUT" >&2
    exit 1
}

"$PYTHON_BIN" - "$OUTPUT" "$POLLER_ID" <<'PY'
from __future__ import print_function
import json
import os
import stat
import sys

path, poller_id = sys.argv[1:3]
mode = stat.S_IMODE(os.stat(path).st_mode)
if mode & 0o077:
    raise SystemExit("server poller output must not be group/world accessible")
with open(path, "r") as handle:
    rows = [line.strip() for line in handle if line.strip()]
if not rows:
    raise SystemExit("server poller output is empty")
payload = json.loads(rows[-1])
if payload.get("schema") != "wwcx.snmp-server-poller.v1":
    raise SystemExit("unexpected server poller schema")
if payload.get("poller_id") != poller_id:
    raise SystemExit("unexpected server poller identity")
if payload.get("source_type") != "host-native":
    raise SystemExit("unexpected server poller source type")
metrics = payload.get("metrics") or {}
required = {"load_1m", "uptime_seconds", "memory_used_percent", "disk_used_percent"}
if not required.issubset(set(metrics)):
    raise SystemExit("required server metrics are missing")
text = json.dumps(payload, sort_keys=True).lower()
for marker in ("password", "passphrase", "community", "private_key", "api_key", "credential"):
    if marker in text:
        raise SystemExit("secret-like field found in server poller output")
print("Shared-host SNMP server poller smoke test passed")
PY
