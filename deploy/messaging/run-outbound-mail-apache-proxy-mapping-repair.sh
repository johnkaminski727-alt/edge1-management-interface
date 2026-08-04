#!/bin/sh
set -eu

umask 077

REPO_ROOT=${REPO_ROOT:-/opt/edge1-management-interface}
ORIGINAL=$REPO_ROOT/deploy/messaging/repair-outbound-mail-phase-b2-apache-proxy-mapping.sh

[ -f "$ORIGINAL" ] && [ ! -L "$ORIGINAL" ] || {
  echo "Reviewed Apache proxy-mapping repair script is absent or unsafe." >&2
  exit 1
}

TEMPORARY=$(mktemp)
cleanup() {
  rm -f -- "$TEMPORARY"
}
trap cleanup EXIT HUP INT TERM

python3 - "$ORIGINAL" "$TEMPORARY" <<'PY'
from pathlib import Path
import sys

source_path = Path(sys.argv[1])
target_path = Path(sys.argv[2])
text = source_path.read_text(encoding="utf-8")
legacy = """  direct_send=$(curl -sS --max-time 5 -H 'Content-Type: application/json' -d '{}' -o /dev/null -w '%{http_code}' http://127.0.0.1:8104/outbound-mail/send || true)
"""
replacement = """  direct_send_body=$(mktemp)
  direct_send=$(curl -sS --max-time 5 -H 'Content-Type: application/json' \\
    --data '{\"to\":[\"apache-repair-canary@example.invalid\"],\"subject\":\"Apache proxy repair disabled-send canary\",\"body\":\"This request must remain disabled.\",\"message_class\":\"business_correspondence\",\"confirm_send\":true}' \\
    -o \"$direct_send_body\" -w '%{http_code}' http://127.0.0.1:8104/outbound-mail/send || true)
  direct_send_error=$(python3 - \"$direct_send_body\" <<'PYJSON'
import json
import sys
with open(sys.argv[1], encoding=\"utf-8\") as handle:
    payload = json.load(handle)
print(payload.get(\"error\", \"\"))
PYJSON
  ) || { rm -f -- \"$direct_send_body\"; fail \"direct send response was not valid JSON\"; }
  rm -f -- \"$direct_send_body\"
"""
if text.count(legacy) != 1:
    raise SystemExit("expected exactly one legacy empty-object send probe")
if "apache-repair-canary@example.invalid" in text:
    raise SystemExit("reviewed script already contains the corrected send probe")
patched = text.replace(legacy, replacement)
old_assertion = '  [ "$direct_send" = 403 ] || fail "direct send endpoint is not HTTP 403"\n'
new_assertion = (
    '  [ "$direct_send" = 403 ] || fail "direct send endpoint is not HTTP 403"\n'
    '  [ "$direct_send_error" = delivery_disabled ] || fail "direct send response is not delivery_disabled"\n'
)
if patched.count(old_assertion) != 1:
    raise SystemExit("expected exactly one direct-send HTTP assertion")
patched = patched.replace(old_assertion, new_assertion)
if patched.count("apache-repair-canary@example.invalid") != 1:
    raise SystemExit("corrected canary payload was not injected exactly once")
if patched.count("direct send response is not delivery_disabled") != 1:
    raise SystemExit("delivery-disabled response assertion was not injected exactly once")
target_path.write_text(patched, encoding="utf-8")
PY

chmod 0700 "$TEMPORARY"
GIT_OPTIONAL_LOCKS=0 sh "$TEMPORARY"
