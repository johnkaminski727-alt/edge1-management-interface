#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON=${WWCX_TIME_AUTHORITY_PYTHON:-python3}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUTPUT=${WWCX_TIME_SOURCE_DISCOVERY_OUTPUT:-"/tmp/wwcx-edge1-time-source-discovery-${STAMP}.json"}

printf '%s\n' '=== WW.CX EDGE1 TIME SOURCE DISCOVERY ==='
printf 'Repository: %s\n' "$ROOT"
printf 'Output:     %s\n' "$OUTPUT"
printf '%s\n' 'Mode:       read-only'
printf '\n'

exec "$PYTHON" "$ROOT/tools/time_authority/discover_edge1_time_sources.py" \
    --samples 5 \
    --local-samples 3 \
    --timeout 1.5 \
    --json-output "$OUTPUT" \
    --pretty \
    "$@"
