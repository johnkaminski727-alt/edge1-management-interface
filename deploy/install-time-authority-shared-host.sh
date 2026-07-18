#!/bin/sh
set -eu

REPO_ROOT=${1:-$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)}
DEST=${WWCX_TIME_AUTHORITY_ROOT:-$HOME/wwcx-time-authority}
PRIVATE_DIR=${WWCX_TIME_AUTHORITY_PRIVATE:-$HOME/private/wwcx-time-authority}

umask 077
mkdir -p "$DEST" "$PRIVATE_DIR"
install -m 0700 "$REPO_ROOT/tools/time_authority/ntp_rtt_probe.py" "$DEST/ntp_rtt_probe.py"
install -m 0700 "$REPO_ROOT/tools/time_authority/collect-shared-host.sh" "$DEST/collect-shared-host.sh"
install -m 0600 "$REPO_ROOT/modules/time-authority/config/sources.json" "$DEST/sources.json"

"$DEST/collect-shared-host.sh" >/dev/null

echo "Shared-host Time Authority collector installed."
echo "Add this cPanel cron entry for 15-minute collection:"
echo "*/15 * * * * $DEST/collect-shared-host.sh >/dev/null 2>&1"
