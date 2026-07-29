#!/usr/bin/env bash
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
POLICY_FILE="${WWCX_DNS_DEFENSE_POLICY:-/etc/wwcx/dns-defense/policy.json}"
STATE_DIR="${WWCX_DNS_DEFENSE_STATE_DIR:-/var/lib/bigbird-networking/dns-defense/staged}"
STATUS_DIR="${WWCX_DNS_DEFENSE_STATUS_DIR:-/var/www/edge1-status}"
STATUS_NAME="dns-defense-policy-status.json"

if [ ! -f "$POLICY_FILE" ]; then
  echo "DNS Defense policy is not configured: $POLICY_FILE" >&2
  exit 3
fi

work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT

"$PYTHON_BIN" "$ROOT/tools/networking/compile-dns-defense-policy.py" \
  --policy "$POLICY_FILE" \
  --output-dir "$work_dir"

zone_file="$(find "$work_dir" -maxdepth 1 -type f -name '*.zone' -print -quit)"
if [ -z "$zone_file" ]; then
  echo "DNS Defense compiler did not produce an RPZ zone" >&2
  exit 1
fi

install -d -m 0755 "$STATE_DIR" "$STATUS_DIR"
install -m 0644 "$zone_file" "$STATE_DIR/$(basename "$zone_file")"
install -m 0644 "$work_dir/wwcx-dns-defense-staged.conf" "$STATE_DIR/wwcx-dns-defense-staged.conf"
install -m 0644 "$work_dir/$STATUS_NAME" "$STATE_DIR/$STATUS_NAME"
install -m 0644 "$work_dir/$STATUS_NAME" "$STATUS_DIR/$STATUS_NAME"

printf '%s\n' "DNS Defense staging artifacts published without activating resolver policy."
