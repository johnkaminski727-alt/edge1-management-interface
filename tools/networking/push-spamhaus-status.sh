#!/usr/bin/env bash
set -euo pipefail

SUMMARY="${BB_SPAMHAUS_SUMMARY:-/var/lib/bigbird-networking/spamhaus/summary.txt}"
URL="${BB_SPAMHAUS_STATUS_URL:-https://ww.cx/api/network-manager-spamhaus-status.php}"

if [ ! -s "$SUMMARY" ]; then
  echo "Missing Spamhaus summary: $SUMMARY" >&2
  exit 1
fi

read -rsp "ww.cx network-manager token: " TOKEN
echo

drop4="$(awk -F= '/^drop4=/{print $2+0}' "$SUMMARY")"
edrop4="$(awk -F= '/^edrop4=/{print $2+0}' "$SUMMARY")"
combined4="$(awk -F= '/^combined4=/{print $2+0}' "$SUMMARY")"
drop6="$(awk -F= '/^drop6=/{print $2+0}' "$SUMMARY")"

service_result="$(systemctl show -p Result --value bigbird-spamhaus-filter.service 2>/dev/null || true)"
timer_state="$(systemctl is-active bigbird-spamhaus-filter.timer 2>/dev/null || true)"
timer_next_run="$(systemctl list-timers --no-legend bigbird-spamhaus-filter.timer 2>/dev/null | awk '{print $1" "$2" "$3" "$4}' || true)"
last_refresh_at="$(date -u -d "@$(stat -c %Y "$SUMMARY")" '+%Y-%m-%dT%H:%M:%SZ')"
observed_at="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

payload="$(python3 - <<PY
import json

combined = int("$combined4")
service_result = "$service_result"

payload = {
    "source_key": "edge1_spamhaus",
    "state": "ok" if combined > 0 and service_result == "success" else "warning",
    "status_message": "Edge1 Spamhaus nftables filter observed from systemd/nftables.",
    "drop4": int("$drop4"),
    "edrop4": int("$edrop4"),
    "combined4": int("$combined4"),
    "drop6": int("$drop6"),
    "drop4_count": int("$drop4"),
    "edrop4_count": int("$edrop4"),
    "combined4_count": int("$combined4"),
    "drop6_count": int("$drop6"),
    "service_state": service_result,
    "timer_state": "$timer_state",
    "timer_next_run": "$timer_next_run",
    "last_refresh_at": "$last_refresh_at",
    "observed_at": "$observed_at",
}

print(json.dumps(payload))
PY
)"

curl -sS -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data "$payload" \
  "$URL" | python3 -m json.tool

echo
echo "Readback:"
curl -sS \
  -H "Authorization: Bearer $TOKEN" \
  "$URL" | python3 -m json.tool
