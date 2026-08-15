#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

command -v python3 >/dev/null 2>&1 || {
    echo "FAIL: python3 is required" >&2
    exit 1
}
command -v chronyc >/dev/null 2>&1 || {
    echo "FAIL: chronyc is required" >&2
    exit 1
}

python3 - "$ROOT" <<'PY'
import importlib.util
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
path = root / "tools" / "time_authority" / "ntp_rtt_probe.py"
spec = importlib.util.spec_from_file_location("ntp_rtt_probe", path)
if spec is None or spec.loader is None:
    raise SystemExit("FAIL: cannot load NTP probe")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

record = probe.probe_source(
    {
        "source_id": "edge1-local-ntp",
        "server_name": "127.0.0.1",
        "port": 123,
        "provider": "WW.CX",
        "region": "Edge1",
        "expected_stratum_min": 1,
        "expected_stratum_max": 15,
    },
    observer_id="edge1-local-smoke",
    observer_host="edge1.ww.cx",
    timeout=3.0,
)
print(json.dumps(record, sort_keys=True))
if not record.get("reachable"):
    raise SystemExit("FAIL: local UDP/123 NTP request did not receive a valid synchronized response")
if record.get("response_mode") != 4:
    raise SystemExit("FAIL: local NTP response was not server mode")
if record.get("leap_indicator") == 3:
    raise SystemExit("FAIL: local NTP server reports unsynchronized leap state")
if not record.get("expectation_ok"):
    raise SystemExit("FAIL: local NTP response stratum is outside the synchronized range")
PY

echo
chronyc tracking
chronyc sources -v

echo
printf '%s\n' "WW.CX Edge1 NTP server smoke test passed."
