#!/usr/bin/env bash
set -euo pipefail

# Edge1 Operator release validation entrypoint.
# Runs non-destructive checks before live installation.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

printf '=== Edge1 Operator Release Validation ===\n'
printf 'Repository: %s\n' "$ROOT_DIR"

[ -f "$ROOT_DIR/deploy/edge1-operator/edge1-operator.service" ] || {
  echo "Missing systemd unit"
  exit 1
}

[ -f "$ROOT_DIR/server/edge1_operator_entrypoint.py" ] || {
  echo "Missing service entrypoint"
  exit 1
}

printf 'Release validation checks passed.\n'
