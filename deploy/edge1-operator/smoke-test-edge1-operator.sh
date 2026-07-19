#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="edge1-operator-mcp.service"

printf '=== Edge1 Operator Smoke Test ===\n'

if systemctl list-unit-files "${SERVICE_NAME}" >/dev/null 2>&1; then
  echo "service unit present"
else
  echo "service unit missing"
  exit 1
fi

systemctl is-enabled "${SERVICE_NAME}" || true
systemctl is-active "${SERVICE_NAME}" || true

printf 'Smoke test completed.\n'
