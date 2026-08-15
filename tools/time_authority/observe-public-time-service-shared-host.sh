#!/bin/sh
set -eu

ROOT=${WWCX_PUBLIC_TIME_OBSERVER_ROOT:-$HOME/wwcx-public-time-observer}
PRIVATE_DIR=${WWCX_PUBLIC_TIME_OBSERVER_PRIVATE:-$HOME/private/wwcx-time-authority}
PUBLIC_DIR=${WWCX_PUBLIC_TIME_STATUS_DIR:-$HOME/shared/wwcx-time-service}
PYTHON_BIN=${WWCX_TIME_AUTHORITY_PYTHON:-python3}
OBSERVER_ID=${WWCX_PUBLIC_TIME_OBSERVER_ID:-business159}
OBSERVER_HOST=${WWCX_PUBLIC_TIME_OBSERVER_HOST:-business159.web-hosting.com}
NTP_HISTORY=${WWCX_PUBLIC_TIME_NTP_HISTORY:-$PRIVATE_DIR/public-service-measurements.jsonl}
NTP_CURRENT=${WWCX_PUBLIC_TIME_NTP_CURRENT:-$PRIVATE_DIR/public-service-current.jsonl}
NTS_CURRENT=${WWCX_PUBLIC_TIME_NTS_CURRENT:-$PRIVATE_DIR/public-nts-current.json}
PUBLIC_STATUS=${WWCX_PUBLIC_TIME_STATUS:-$PUBLIC_DIR/public-status.json}
EXPECTED_FILE=${WWCX_PUBLIC_TIME_NTS_EXPECTED_FILE:-$ROOT/nts-expected}

umask 077
mkdir -p "$PRIVATE_DIR" "$PUBLIC_DIR"

NTP_RC=0
"$PYTHON_BIN" "$ROOT/ntp_rtt_probe.py" \
  --observer-id "$OBSERVER_ID" \
  --observer-host "$OBSERVER_HOST" \
  --sources "$ROOT/public-service-sources.json" \
  --output "$NTP_HISTORY" > "$NTP_CURRENT" || NTP_RC=$?

NTS_RC=0
"$PYTHON_BIN" "$ROOT/nts_ke_probe.py" \
  --observer-id "$OBSERVER_ID" \
  --observer-host "$OBSERVER_HOST" \
  --server-name ntp.ww.cx \
  --port 4460 \
  --output "$NTS_CURRENT" >/dev/null || NTS_RC=$?

NTS_EXPECTED=0
if [ -r "$EXPECTED_FILE" ]; then
  NTS_EXPECTED=$(cat "$EXPECTED_FILE" 2>/dev/null || printf '0')
fi
case "$NTS_EXPECTED" in
  1|yes|YES|true|TRUE) NTS_FLAG=--nts-expected ;;
  *) NTS_FLAG= ;;
esac

"$PYTHON_BIN" "$ROOT/build_public_time_status.py" \
  --ntp-current "$NTP_CURRENT" \
  --nts-current "$NTS_CURRENT" \
  --output "$PUBLIC_STATUS" \
  --observer-id "$OBSERVER_ID" \
  --observer-host "$OBSERVER_HOST" \
  $NTS_FLAG >/dev/null

# NTP reachability is the core observer requirement. NTS may legitimately be
# unavailable until the separate NTS activation is approved and completed.
if [ "$NTP_RC" -ne 0 ]; then
  exit "$NTP_RC"
fi
if [ -n "$NTS_FLAG" ] && [ "$NTS_RC" -ne 0 ]; then
  exit "$NTS_RC"
fi
exit 0
