#!/bin/sh
set -eu

INSTALL_ROOT=${WWCX_TIME_AUTHORITY_ROOT:-$HOME/wwcx-time-authority}
OUTPUT=${WWCX_TIME_AUTHORITY_OUTPUT:-$HOME/private/wwcx-time-authority/measurements.jsonl}

umask 077
mkdir -p "$(dirname "$OUTPUT")"

exec /usr/bin/env python3 "$INSTALL_ROOT/ntp_rtt_probe.py" \
  --observer-id shared-host \
  --observer-host business159.web-hosting.com \
  --sources "$INSTALL_ROOT/sources.json" \
  --output "$OUTPUT"
