#!/usr/bin/env bash
set -euo pipefail
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
python3 -m py_compile \
  "$ROOT/server/network_sensor_exporter.py" \
  "$ROOT/server/security_correlation_sensor_exporter.py" \
  "$ROOT/server/network_defense_sensor_exporter.py"
python3 "$ROOT/tests/test_network_sensor_exporter.py"
python3 "$ROOT/tests/test_network_sensor_correlation_integration.py"
python3 "$ROOT/tests/test_network_sensor_network_defense_integration.py"
for file in "$ROOT"/tools/networking/network-sensor-*.sh "$ROOT"/tools/networking/discover-edge1-network-sensor.sh "$ROOT"/deploy/install-edge1-network-sensor.sh; do
  bash -n "$file"
  sh -n "$file"
done
python3 - "$ROOT" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
for path in (root / 'deploy/systemd').glob('wwcx-network-sensor-*'):
    text = path.read_text(encoding='utf-8', errors='replace')
    assert 'ExecStart=' in text or path.suffix == '.timer'

correlation = (root / 'deploy/systemd/wwcx-security-correlation.service').read_text(encoding='utf-8')
assert 'security_correlation_sensor_exporter.py' in correlation
network_defense = (root / 'deploy/systemd/wwcx-network-defense.service').read_text(encoding='utf-8')
assert 'network_defense_sensor_exporter.py' in network_defense

suricata = (root / 'deploy/systemd/wwcx-network-sensor-suricata.service').read_text(encoding='utf-8')
for marker in (
    'User=suricata',
    'Group=suricata',
    'ExecStartPre=+/usr/bin/install -d -o root -g root -m 0755 /var/log/wwcx-network-sensor',
    'ExecStartPre=+/usr/bin/install -d -o suricata -g root -m 2770 /var/log/wwcx-network-sensor/suricata',
    'ExecStartPre=+/usr/bin/install -d -o wwsensor -g root -m 2770 /var/log/wwcx-network-sensor/zeek',
    'ReadWritePaths=/var/log/wwcx-network-sensor /run/wwcx-network-sensor',
    'UMask=0007',
):
    assert marker in suricata, marker
for forbidden in ('--user=suricata', '--group=suricata', 'CAP_CHOWN', 'CAP_SETUID', 'CAP_SETGID'):
    assert forbidden not in suricata, forbidden

pcap = (root / 'deploy/systemd/wwcx-network-sensor-pcap.service').read_text(encoding='utf-8')
for marker in (
    'User=wwsensor',
    'Group=wwsensor',
    'ExecStartPre=+/usr/bin/install -d -o root -g root -m 0755 /var/lib/wwcx-network-sensor',
    'ExecStartPre=+/usr/bin/install -d -o wwsensor -g root -m 2770 /var/lib/wwcx-network-sensor/pcap',
    'ExecStartPre=+/usr/bin/install -d -o wwsensor -g root -m 2770 /var/lib/wwcx-network-sensor/extracted',
    'ReadWritePaths=/var/lib/wwcx-network-sensor',
    'UMask=0007',
):
    assert marker in pcap, marker
for forbidden in ('CAP_CHOWN', 'CAP_SETUID', 'CAP_SETGID'):
    assert forbidden not in pcap, forbidden

pcap_wrapper = (root / 'tools/networking/network-sensor-pcap.sh').read_text(encoding='utf-8')
assert '-Z wwsensor' not in pcap_wrapper
assert '/usr/bin/tcpdump' in pcap_wrapper

zeek = (root / 'deploy/systemd/wwcx-network-sensor-zeek.service').read_text(encoding='utf-8')
for marker in (
    'ExecStartPre=+/usr/bin/install -d -o wwsensor -g root -m 2770 /var/log/wwcx-network-sensor/zeek',
    'ExecStartPre=+/usr/bin/install -d -o wwsensor -g root -m 2770 /var/lib/wwcx-network-sensor/extracted',
    'ReadWritePaths=/var/log/wwcx-network-sensor /var/lib/wwcx-network-sensor',
    'UMask=0007',
):
    assert marker in zeek, marker

runtime_files = [
    root / 'config/network-sensor/owner-full.env',
    root / 'config/network-sensor/wwcx-owner-full.zeek',
    root / 'deploy/install-edge1-network-sensor.sh',
    root / 'deploy/systemd/wwcx-security-correlation.service',
    root / 'deploy/systemd/wwcx-network-defense.service',
    root / 'server/network_sensor_exporter.py',
    root / 'server/security_correlation_sensor_exporter.py',
    root / 'server/network_defense_sensor_exporter.py',
    root / 'tools/networking/discover-edge1-network-sensor.sh',
    root / 'tools/networking/network-sensor-pcap.sh',
    root / 'tools/networking/network-sensor-prune.sh',
    root / 'tools/networking/network-sensor-zeek.sh',
]
runtime_files.extend(sorted((root / 'deploy/systemd').glob('wwcx-network-sensor-*')))

forbidden_commands = (
    'iptables -F',
    'nft flush ruleset',
    'ip route add',
    'ip route del',
    'sysctl -w net.ipv4.ip_forward=1',
)
for path in runtime_files:
    assert path.is_file(), path
    text = path.read_text(encoding='utf-8', errors='replace')
    for forbidden in forbidden_commands:
        assert forbidden not in text, (forbidden, path)

print('Static network sensor validation passed.')
PY
