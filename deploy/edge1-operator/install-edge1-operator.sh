#!/usr/bin/env bash
set -euo pipefail

# Edge1 Operator bootstrap installer.
# This script prepares the host-side runtime only. It does not contain
# credentials, tokens, or private connection material.

SERVICE_USER="edge1-operator"
INSTALL_ROOT="/opt/edge1-management-interface"
SERVICE_NAME="edge1-operator-mcp"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root or through sudo." >&2
  exit 1
fi

if ! id "${SERVICE_USER}" >/dev/null 2>&1; then
  useradd --system --home /var/lib/${SERVICE_USER} --shell /usr/sbin/nologin "${SERVICE_USER}"
fi

install -d -o "${SERVICE_USER}" -g "${SERVICE_USER}" /var/lib/${SERVICE_USER}/evidence

cat <<EOF
Edge1 Operator bootstrap prepared.

Repository expected at:
  ${INSTALL_ROOT}

Next steps:
  1. install the systemd unit
  2. configure private transport credentials outside Git
  3. start ${SERVICE_NAME}
  4. run health validation
EOF
