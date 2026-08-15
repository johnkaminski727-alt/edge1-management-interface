#!/bin/sh
set -eu

REPO_ROOT=${1:-$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)}
DEST=${WWCX_PUBLIC_TIME_OBSERVER_ROOT:-$HOME/wwcx-public-time-observer}
PRIVATE_DIR=${WWCX_PUBLIC_TIME_OBSERVER_PRIVATE:-$HOME/private/wwcx-time-authority}
PUBLIC_DIR=${WWCX_PUBLIC_TIME_STATUS_DIR:-$HOME/shared/wwcx-time-service}
PYTHON_BIN=${WWCX_TIME_AUTHORITY_PYTHON:-python3}

for command_name in "$PYTHON_BIN" install grep crontab; do
  command -v "$command_name" >/dev/null 2>&1 || {
    echo "Missing required command: $command_name" >&2
    exit 1
  }
done

"$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 6):
    raise SystemExit("WW.CX public time observer requires Python 3.6 or newer")
PY

umask 077
mkdir -p "$DEST" "$PRIVATE_DIR" "$PUBLIC_DIR"
install -m 0700 "$REPO_ROOT/tools/time_authority/ntp_rtt_probe.py" "$DEST/ntp_rtt_probe.py"
install -m 0700 "$REPO_ROOT/tools/time_authority/nts_ke_probe.py" "$DEST/nts_ke_probe.py"
install -m 0700 "$REPO_ROOT/tools/time_authority/build_public_time_status.py" "$DEST/build_public_time_status.py"
install -m 0700 "$REPO_ROOT/tools/time_authority/observe-public-time-service-shared-host.sh" "$DEST/observe-public-time-service.sh"
install -m 0600 "$REPO_ROOT/modules/time-authority/config/public-service-sources.json" "$DEST/public-service-sources.json"

if [ -n "${WWCX_NTS_EXPECTED+x}" ]; then
  case "$WWCX_NTS_EXPECTED" in
    0|1) printf '%s\n' "$WWCX_NTS_EXPECTED" > "$DEST/nts-expected" ;;
    *) echo "WWCX_NTS_EXPECTED must be 0 or 1" >&2; exit 1 ;;
  esac
elif [ ! -e "$DEST/nts-expected" ]; then
  printf '0\n' > "$DEST/nts-expected"
fi
chmod 0600 "$DEST/nts-expected"

WWCX_TIME_AUTHORITY_PYTHON="$PYTHON_BIN" "$DEST/observe-public-time-service.sh" >/dev/null

CRON_LINE="*/5 * * * * WWCX_TIME_AUTHORITY_PYTHON=$PYTHON_BIN $DEST/observe-public-time-service.sh >/dev/null 2>&1"
if [ "${WWCX_PUBLIC_TIME_INSTALL_CRON:-1}" = "1" ]; then
  EXISTING_CRONTAB=$(crontab -l 2>/dev/null || true)
  if ! printf '%s\n' "$EXISTING_CRONTAB" | grep -Fqx "$CRON_LINE"; then
    {
      test -z "$EXISTING_CRONTAB" || printf '%s\n' "$EXISTING_CRONTAB"
      printf '%s\n' "$CRON_LINE"
    } | crontab -
  fi
fi

WWCX_TIME_AUTHORITY_PYTHON="$PYTHON_BIN" \
WWCX_PUBLIC_TIME_OBSERVER_ROOT="$DEST" \
WWCX_PUBLIC_TIME_OBSERVER_PRIVATE="$PRIVATE_DIR" \
WWCX_PUBLIC_TIME_STATUS_DIR="$PUBLIC_DIR" \
  "$REPO_ROOT/deploy/public-time-observer-shared-host-smoke-test.sh"

printf '%s\n' \
  "Business159 public WW.CX time observer installed and verified." \
  "Observer root: $DEST" \
  "Private measurement history: $PRIVATE_DIR/public-service-measurements.jsonl" \
  "Sanitized public status: $PUBLIC_DIR/public-status.json" \
  "Schedule: every 5 minutes" \
  "NTS expected flag: $(cat "$DEST/nts-expected")"
