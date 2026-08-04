#!/usr/bin/env bash
set -euo pipefail
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
python3 -m py_compile \
  "$ROOT/server/network_sensor_exporter.py" \
  "$ROOT/server/network_sensor_capture_acceptance.py" \
  "$ROOT/server/security_correlation_sensor_exporter.py" \
  "$ROOT/server/network_defense_sensor_exporter.py"
python3 "$ROOT/tests/test_network_sensor_exporter.py"
python3 "$ROOT/tests/test_network_sensor_capture_acceptance.py"
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

sensor_defaults = (root / 'config/network-sensor/owner-full.env').read_text(encoding='utf-8')
assert 'SURICATA_CAPTURE_ARGUMENT=--af-packet=CHANGE_ME' in sensor_defaults

suricata = (root / 'deploy/systemd/wwcx-network-sensor-suricata.service').read_text(encoding='utf-8')
for marker in (
    'ExecStartPre=+/usr/bin/install -d -o root -g root -m 0755 /var/log/wwcx-network-sensor',
    'ExecStartPre=+/usr/bin/install -d -o suricata -g root -m 2770 /var/log/wwcx-network-sensor/suricata',
    'ExecStartPre=+/usr/bin/chown -R suricata:root /var/log/wwcx-network-sensor/suricata',
    'ExecStartPre=+/usr/bin/install -d -o wwsensor -g root -m 2770 /var/log/wwcx-network-sensor/zeek',
    'ExecStart=/usr/bin/suricata ${SURICATA_CAPTURE_ARGUMENT}',
    '--user=suricata',
    '--group=suricata',
    'ReadWritePaths=/var/log/wwcx-network-sensor /run/wwcx-network-sensor',
    'CapabilityBoundingSet=CAP_CHOWN CAP_SETGID CAP_SETUID CAP_SETPCAP CAP_NET_ADMIN CAP_NET_RAW CAP_SYS_NICE',
    'UMask=0007',
):
    assert marker in suricata, marker
assert '--af-packet=${SENSOR_INTERFACE}' not in suricata
assert '--pcap=${SENSOR_INTERFACE}' not in suricata
assert 'AmbientCapabilities=' not in suricata
assert 'User=suricata' not in suricata
assert 'Group=suricata' not in suricata

pcap = (root / 'deploy/systemd/wwcx-network-sensor-pcap.service').read_text(encoding='utf-8')
for marker in (
    'User=root',
    'Group=root',
    'ExecStartPre=+/usr/bin/install -d -o root -g root -m 0755 /var/lib/wwcx-network-sensor',
    'ExecStartPre=+/usr/bin/install -d -o wwsensor -g root -m 2770 /var/lib/wwcx-network-sensor/pcap',
    'ExecStartPre=+/usr/bin/install -d -o wwsensor -g root -m 2770 /var/lib/wwcx-network-sensor/extracted',
    'ReadWritePaths=/var/lib/wwcx-network-sensor',
    'CapabilityBoundingSet=CAP_CHOWN CAP_SETGID CAP_SETUID CAP_NET_ADMIN CAP_NET_RAW',
    'UMask=0007',
):
    assert marker in pcap, marker
assert 'AmbientCapabilities=' not in pcap

pcap_wrapper = (root / 'tools/networking/network-sensor-pcap.sh').read_text(encoding='utf-8')
assert '-Z wwsensor' in pcap_wrapper
assert '/usr/bin/tcpdump' in pcap_wrapper

zeek = (root / 'deploy/systemd/wwcx-network-sensor-zeek.service').read_text(encoding='utf-8')
for marker in (
    'ExecStartPre=+/usr/bin/install -d -o wwsensor -g root -m 2770 /var/log/wwcx-network-sensor/zeek',
    'ExecStartPre=+/usr/bin/install -d -o wwsensor -g root -m 2770 /var/lib/wwcx-network-sensor/extracted',
    'ReadWritePaths=/var/log/wwcx-network-sensor /var/lib/wwcx-network-sensor',
    'UMask=0007',
):
    assert marker in zeek, marker

installer = (root / 'deploy/install-edge1-network-sensor.sh').read_text(encoding='utf-8')
for marker in (
    'SURICATA_CAPTURE_BACKEND=af-packet',
    '[ "$ALLOW_ADDRESSED" = true ] && SURICATA_CAPTURE_BACKEND=pcap',
    'SURICATA_CAPTURE_ARGUMENT=$suricata_capture_argument',
    'network_sensor_capture_acceptance.py',
    'suricata-capture-acceptance.json',
    '--startup-wait-seconds 75',
    '--observation-seconds 30',
):
    assert marker in installer, marker

runtime_files = [
    root / 'config/network-sensor/owner-full.env',
    root / 'config/network-sensor/wwcx-owner-full.zeek',
    root / 'deploy/install-edge1-network-sensor.sh',
    root / 'deploy/systemd/wwcx-security-correlation.service',
    root / 'deploy/systemd/wwcx-network-defense.service',
    root / 'server/network_sensor_exporter.py',
    root / 'server/network_sensor_capture_acceptance.py',
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
