#!/usr/bin/env bash
# Check-only Spamhaus DROP JSON staging. Production activation is deliberately blocked.
set -Eeuo pipefail

MODE="${1:---check-only}"
if [ "$#" -gt 1 ] || [ "$MODE" != "--check-only" ]; then
  echo "STOP: only --check-only is supported; activation requires separate review" >&2
  exit 2
fi

ROOT="${EDGE1_MANAGEMENT_ROOT:-/opt/edge1-management-interface}"
PARSER="$ROOT/tools/networking/spamhaus_feed_candidate.py"
NFT="${NFT:-/usr/sbin/nft}"
CURL="${CURL:-/usr/bin/curl}"
PYTHON="${PYTHON:-/usr/bin/python3}"
V4_URL="https://www.spamhaus.org/drop/drop_v4.json"
V6_URL="https://www.spamhaus.org/drop/drop_v6.json"

if [ "$EUID" -ne 0 ]; then
  echo "STOP: run as root for nftables check-only validation" >&2
  exit 1
fi
for program in "$NFT" "$CURL" "$PYTHON"; do
  if [ ! -x "$program" ]; then echo "Missing executable: $program" >&2; exit 1; fi
done
if [ ! -r "$PARSER" ]; then echo "Missing JSON parser: $PARSER" >&2; exit 1; fi

# Do not silently carry forward obsolete text/eDROP overrides.
for legacy in BB_SPAMHAUS_DROP_URL BB_SPAMHAUS_EDROP_URL BB_SPAMHAUS_DROPV6_URL; do
  if [ -n "${!legacy+x}" ]; then
    echo "STOP: obsolete feed override $legacy is unsupported" >&2
    exit 1
  fi
done

# Avoid validating a new-table candidate against a machine that has an existing filter.
if "$NFT" list table inet bigbird_spamhaus >/dev/null 2>&1; then
  echo "STOP: existing Spamhaus table requires separate migration review" >&2
  exit 1
fi

umask 077
WORK="$(mktemp -d /tmp/edge1-spamhaus-json.XXXXXXXX)"
trap 'rm -rf "$WORK"' EXIT

fetch() {
  local url="$1" output="$2"
  "$CURL" --fail --silent --show-error --location --retry 2 --retry-delay 3 \
    --connect-timeout 15 --max-time 90 --max-filesize 8388608 \
    --user-agent "Edge1SpamhausJSONPreflight/1.0" \
    --output "$output" "$url"
  if [ "$(stat -c %s "$output")" -gt 8388608 ]; then
    echo "STOP: feed exceeds maximum bytes" >&2
    exit 1
  fi
}

echo "=== Fetch current official JSON DROP feeds ==="
fetch "$V4_URL" "$WORK/ipv4.json"
fetch "$V6_URL" "$WORK/ipv6.json"
echo "=== Validate and render offline candidate ==="
"$PYTHON" "$PARSER" --ipv4 "$WORK/ipv4.json" --ipv6 "$WORK/ipv6.json" \
  --output "$WORK/candidate.nft" --summary "$WORK/summary.txt"
echo "=== nftables check-only syntax validation ==="
"$NFT" --check --file "$WORK/candidate.nft"
echo "PASS: feed and candidate verified; nothing applied or persisted"
