#!/bin/sh
set -eu

HOST=${HOST:-127.0.0.1}
PORT=${PORT:-8104}
BASE_URL="http://$HOST:$PORT"
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT HUP INT TERM

curl -fsS "$BASE_URL/outbound-mail/healthz" > "$TMP_DIR/health.json"
curl -fsS "$BASE_URL/outbound-mail/status" > "$TMP_DIR/status.json"

python3 - "$TMP_DIR/health.json" "$TMP_DIR/status.json" <<'PY'
import json
import pathlib
import sys

health = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
status = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8"))
assert health == {"gateway": "wwcx-outbound-mail-gateway", "status": "ok"}
assert status["gateway"] == "wwcx-outbound-mail-gateway"
assert status["state"] == "disabled"
assert status["external_delivery_enabled"] is False
assert status["policy_enabled"] is False
assert status["preparation_api"]["enabled"] is False
assert status["preparation_api"]["runtime_secret_configured"] is False
assert status["sender_selection"]["outbound_activation_authorized"] is False
assert status["sender_selection"]["live_sender_count"] == 0
assert not any(item["ready"] for item in status["providers"])
PY

api_status_code=$(curl -sS -o "$TMP_DIR/api-status.json" -w '%{http_code}' \
  "$BASE_URL/outbound-mail/api/v1/status")
if [ "$api_status_code" != "403" ]; then
  echo "Expected disabled preparation API to return 403; got $api_status_code" >&2
  cat "$TMP_DIR/api-status.json" >&2
  exit 1
fi
python3 - "$TMP_DIR/api-status.json" <<'PY'
import json
import pathlib
import sys
payload = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
assert payload["error"] == "preparation_api_disabled"
PY

send_status_code=$(curl -sS -o "$TMP_DIR/send.json" -w '%{http_code}' \
  -H 'Content-Type: application/json' \
  --data-binary '{"system_generated":true,"to":"phase-a-no-send@example.invalid","subject":"Phase A no-send probe","body":"This request must be rejected before external delivery.","message_class":"business_correspondence","mailing_address":"151 2 Street South, Invermay, SK","confirm_send":true}' \
  "$BASE_URL/outbound-mail/send")
if [ "$send_status_code" != "403" ]; then
  echo "Expected live delivery to return 403; got $send_status_code" >&2
  cat "$TMP_DIR/send.json" >&2
  exit 1
fi
python3 - "$TMP_DIR/send.json" <<'PY'
import json
import pathlib
import sys
payload = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
assert payload["error"] == "delivery_disabled"
PY

if ! ss -H -lnt | awk -v suffix=":$PORT" '$4 ~ suffix "$" {found=1} END {exit found ? 0 : 1}'; then
  echo "No TCP listener found on port $PORT" >&2
  exit 1
fi

if ss -H -lnt | awk -v suffix=":$PORT" '
  $4 ~ suffix "$" && $4 !~ /^127[.]0[.]0[.]1:/ && $4 !~ /^\[::1\]:/ {unsafe=1}
  END {exit unsafe ? 0 : 1}
'; then
  echo "Unsafe non-loopback listener detected on port $PORT" >&2
  ss -lntp | grep ":$PORT" >&2 || true
  exit 1
fi

printf '%s\n' "Outbound mail gateway disabled-state smoke test passed"
printf '%s\n' "Listener: $HOST:$PORT"
printf '%s\n' "Preparation API: disabled"
printf '%s\n' "External delivery: rejected"
