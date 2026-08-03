#!/usr/bin/env bash
set -euo pipefail
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
python3 -m py_compile "$ROOT/server/network_sensor_exporter.py"
python3 "$ROOT/tests/test_network_sensor_exporter.py"
for file in "$ROOT"/tools/networking/network-sensor-*.sh "$ROOT"/tools/networking/discover-edge1-network-sensor.sh "$ROOT"/deploy/install-edge1-network-sensor.sh; do bash -n "$file"; done
python3 - "$ROOT" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])
for path in (root/'deploy/systemd').glob('wwcx-network-sensor-*'):
    text=path.read_text()
    assert 'ExecStart=' in text or path.suffix=='.timer'
for forbidden in ('iptables -F','nft flush','ip route add','ip route del','sysctl -w net.ipv4.ip_forward=1'):
    for path in root.rglob('*'):
        if path.is_file() and path.name != 'validate-edge1-network-sensor.sh':
            assert forbidden not in path.read_text(errors='ignore'), (forbidden,path)
print('Static network sensor validation passed.')
PY
