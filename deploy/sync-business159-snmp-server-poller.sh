#!/bin/sh
set -eu

umask 077

SSH_WRAPPER=/usr/local/libexec/business159-tunnel/ssh
SSH_CONFIG=/etc/business159-operator/ssh_config
KNOWN_HOSTS=/etc/business159-operator/known_hosts
REMOTE_ALIAS=business159
REMOTE_PATH=/home/wwcxjywl/private/wwcx-snmp-server-poller/measurements.jsonl
DEST_DIR=/var/lib/edge1-snmp/server-pollers
DEST=$DEST_DIR/business159-measurements.jsonl
POLLER_MODULE=/usr/local/libexec/edge1-snmp/edge1_snmp_server_pollers.py
EXPECTED_POLLER=business159-shared-host
EXPECTED_HOST=business159.web-hosting.com
MAX_RECORDS=576
MAX_BYTES=2097152

[ "$(id -u)" -eq 0 ] || { echo "Business159 SNMP telemetry sync must run as root" >&2; exit 20; }
[ -x "$SSH_WRAPPER" ] || { echo "Business159 strict SSH wrapper unavailable" >&2; exit 21; }
[ -r "$SSH_CONFIG" ] || { echo "Business159 SSH config unavailable" >&2; exit 22; }
[ -r "$KNOWN_HOSTS" ] || { echo "Business159 known_hosts unavailable" >&2; exit 23; }
[ -r "$POLLER_MODULE" ] || { echo "SNMP server poller validator unavailable" >&2; exit 24; }
[ -d "$DEST_DIR" ] || { echo "SNMP server-poller import directory unavailable" >&2; exit 25; }

owner=$(stat -c '%U:%G' "$DEST_DIR")
mode=$(stat -c '%a' "$DEST_DIR")
[ "$owner" = 'wwadmin:wwadmin' ] || { echo "unexpected import directory owner: $owner" >&2; exit 26; }
[ "$mode" = '700' ] || { echo "unexpected import directory mode: $mode" >&2; exit 27; }

TMP=$(mktemp "$DEST_DIR/.business159-measurements.XXXXXX")
cleanup() {
    rm -f "$TMP"
}
trap cleanup EXIT HUP INT TERM

"$SSH_WRAPPER" \
    -o BatchMode=yes \
    -o StrictHostKeyChecking=yes \
    "$REMOTE_ALIAS" \
    "tail -n $MAX_RECORDS '$REMOTE_PATH'" \
    > "$TMP"

[ -s "$TMP" ] || { echo "Business159 telemetry fetch returned no records" >&2; exit 28; }
bytes=$(wc -c < "$TMP" | tr -d ' ')
[ "$bytes" -le "$MAX_BYTES" ] || { echo "Business159 telemetry exceeds bounded transfer size" >&2; exit 29; }

/usr/bin/python3 - "$TMP" "$POLLER_MODULE" "$EXPECTED_POLLER" "$EXPECTED_HOST" "$MAX_RECORDS" <<'PY'
from __future__ import print_function
import importlib.util
import json
import sys

path, module_path, expected_poller, expected_host, max_records_text = sys.argv[1:]
max_records = int(max_records_text)

spec = importlib.util.spec_from_file_location("edge1_snmp_server_pollers", module_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

with open(path, "r", encoding="utf-8") as handle:
    rows = [line.strip() for line in handle if line.strip()]

if not rows:
    raise SystemExit("Business159 telemetry contains no records")
if len(rows) > max_records:
    raise SystemExit("Business159 telemetry exceeds record bound")

latest = None
markers = ("password", "passphrase", "community", "private_key", "api_key", "credential")
for raw in rows:
    lowered = raw.lower()
    for marker in markers:
        if marker in lowered:
            raise SystemExit("secret-like marker found in Business159 telemetry")
    payload = json.loads(raw)
    module.validate_snapshot(payload)
    if payload.get("poller_id") != expected_poller:
        raise SystemExit("unexpected Business159 poller identity")
    if payload.get("observer_host") != expected_host:
        raise SystemExit("unexpected Business159 observer host")
    if payload.get("source_type") != "host-native":
        raise SystemExit("unexpected Business159 telemetry source type")
    latest = payload.get("generated_at")

print("records=%d" % len(rows))
print("latest_generated_at=%s" % latest)
print("schema_validation=PASS")
PY

chown wwadmin:wwadmin "$TMP"
chmod 0600 "$TMP"
mv -f "$TMP" "$DEST"
trap - EXIT HUP INT TERM

printf 'destination=%s\n' "$DEST"
printf 'records=%s\n' "$(wc -l < "$DEST" | tr -d ' ')"
printf 'bytes=%s\n' "$(wc -c < "$DEST" | tr -d ' ')"
printf 'sha256=%s\n' "$(sha256sum "$DEST" | awk '{print $1}')"
printf 'business159_snmp_server_poller_sync=PASS\n'
