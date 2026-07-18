#!/bin/sh
set -eu

REPO_ROOT=${EDGE1_MANAGEMENT_ROOT:-/opt/edge1-management-interface}
OUTPUT=${EDGE1_TIME_AUTHORITY_OUTPUT:-/var/lib/edge1-time-authority/measurements.jsonl}

exec /usr/bin/python3 "$REPO_ROOT/tools/time_authority/ntp_rtt_probe.py" \
  --observer-id edge1 \
  --observer-host edge1.ww.cx \
  --sources "$REPO_ROOT/modules/time-authority/config/sources.json" \
  --output "$OUTPUT"
