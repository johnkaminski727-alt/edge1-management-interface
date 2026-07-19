#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
PLAN="$ROOT/docs/telecom/wwcx-sip-interconnect-staging-plan.md"
CFG="$ROOT/deploy/interconnect/kamailio/kamailio-staging.cfg"
TLS="$ROOT/deploy/interconnect/kamailio/wwcx-tls-staging.cfg.example"
PREFLIGHT="$ROOT/deploy/interconnect/preflight-readonly.sh"

for file in "$PLAN" "$CFG" "$TLS" "$PREFLIGHT"; do
  test -s "$file" || { echo "missing or empty: $file" >&2; exit 1; }
done

# Guardrails: staging config must remain loopback-only and deny registration.
grep -F 'listen=tls:127.0.0.1:5061' "$CFG" >/dev/null
grep -F 'Public Registration Disabled' "$CFG" >/dev/null
grep -F 'Interconnect Not Yet Activated' "$CFG" >/dev/null

# Ensure no private key material or obvious secret placeholders are committed.
if grep -R -E -- 'BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY|password[[:space:]]*=|secret[[:space:]]*=' \
  "$ROOT/deploy/interconnect" "$ROOT/docs/telecom" >/dev/null 2>&1; then
  echo 'possible secret or private key material detected' >&2
  exit 1
fi

# Shell syntax checks.
sh -n "$PREFLIGHT"
sh -n "$ROOT/deploy/interconnect/validate-staging-assets.sh"

echo 'WW.CX SIP interconnect staging asset validation passed'
