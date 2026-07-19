#!/bin/sh
set -eu

BASE_URL=${BASE_URL:-http://127.0.0.1:8096}
TMP_STATUS=$(mktemp)
trap 'rm -f "$TMP_STATUS"' EXIT

curl -fsS "$BASE_URL/healthz" | python3 -m json.tool >/dev/null
curl -fsS "$BASE_URL/api/telephony/status" >"$TMP_STATUS"
python3 - "$TMP_STATUS" <<'PY'
import json
import sys
from pathlib import Path
payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
required = {"schema_version", "generated_at", "mode", "site", "overall_status", "metrics", "services", "interconnects", "registrations", "alerts"}
missing = sorted(required - payload.keys())
if missing:
    raise SystemExit("status payload missing: " + ", ".join(missing))
if payload["mode"] != "live_read_only":
    raise SystemExit("expected live_read_only mode")
if payload["overall_status"] not in {"healthy", "degraded", "critical", "unknown"}:
    raise SystemExit("invalid overall status")
print("telephony status API smoke test passed")
PY

if ss -lnt | grep -E '0\.0\.0\.0:8096|\[::\]:8096' >/dev/null; then
  echo "ERROR: telephony console is publicly bound" >&2
  exit 1
fi

echo "telephony console loopback guard passed"
