#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPECTED_ROOT="/opt/edge1-management-interface"
SERVICE_SRC="$REPO_ROOT/deploy/systemd/edge1-private-library-search.service"
SERVICE_DST="/etc/systemd/system/edge1-private-library-search.service"

if [ "${EUID}" -ne 0 ]; then
  echo "install-private-library-search-service.sh must run as root" >&2
  exit 1
fi

for command in /usr/bin/python3 /bin/systemctl; do
  if [ ! -x "$command" ]; then
    echo "Missing required command: $command" >&2
    exit 1
  fi
done

if [ "$REPO_ROOT" != "$EXPECTED_ROOT" ]; then
  echo "Warning: repo checkout is $REPO_ROOT, but the unit file targets $EXPECTED_ROOT." >&2
  echo "Either install the repo at $EXPECTED_ROOT or edit the unit file paths before installing." >&2
  exit 1
fi

if [ ! -x "$REPO_ROOT/bin/run_private_library_search.sh" ]; then
  echo "Missing or non-executable: $REPO_ROOT/bin/run_private_library_search.sh" >&2
  exit 1
fi

install -m 0644 "$SERVICE_SRC" "$SERVICE_DST"

systemctl daemon-reload
systemctl enable --now edge1-private-library-search.service
systemctl --no-pager --full status edge1-private-library-search.service
