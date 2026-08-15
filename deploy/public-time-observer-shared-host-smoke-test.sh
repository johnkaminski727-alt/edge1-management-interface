#!/bin/sh
set -eu

ROOT=${WWCX_PUBLIC_TIME_OBSERVER_ROOT:-$HOME/wwcx-public-time-observer}
PUBLIC_STATUS=${WWCX_PUBLIC_TIME_STATUS:-${WWCX_PUBLIC_TIME_STATUS_DIR:-$HOME/shared/wwcx-time-service}/public-status.json}
PYTHON_BIN=${WWCX_TIME_AUTHORITY_PYTHON:-python3}

"$ROOT/observe-public-time-service.sh"

[ -s "$PUBLIC_STATUS" ] || {
  echo "Public time observer status is missing: $PUBLIC_STATUS" >&2
  exit 1
}

"$PYTHON_BIN" - "$PUBLIC_STATUS" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)

assert payload.get("schema_version") == 1
assert payload.get("service", {}).get("canonical_host") == "ntp.ww.cx"
assert payload.get("service", {}).get("alternate_hosts") == ["time.ww.cx"]
assert payload.get("observer", {}).get("id") == "business159"
assert payload.get("observer", {}).get("host") == "business159.web-hosting.com"
ntp = payload.get("ntp", {})
assert ntp.get("reachable") is True
assert ntp.get("resolved_address")
assert isinstance(ntp.get("stratum"), int) and 1 <= ntp["stratum"] <= 15
assert ntp.get("leap_indicator") != 3
assert ntp.get("ntp_version") in (3, 4)
nts = payload.get("nts", {})
if nts.get("expected"):
    assert nts.get("reachable") is True
    assert nts.get("tls_verified") is True
    assert nts.get("alpn") == "ntske/1"
for forbidden in ("private_key", "certificate_key", "credentials", "password", "token"):
    assert forbidden not in json.dumps(payload).lower()
PY

echo "Business159 public time observer smoke test passed."
