#!/usr/bin/env bash
# Fail closed: legacy installer installs a timed firewall-changing updater.
set -Eeuo pipefail
echo "STOP: automatic Spamhaus filtering is not authorized by the JSON staging release." >&2
echo "For offline feed validation run: sudo bash /opt/edge1-management-interface/tools/networking/spamhaus-nft-update.sh --check-only" >&2
echo "A separately reviewed, backup-protected activation installer is required." >&2
exit 1
