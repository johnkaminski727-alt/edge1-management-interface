#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).parents[1]
INSTALLER = ROOT / 'deploy' / 'install-spamhaus-live-state-observability.sh'
VERIFIER = ROOT / 'server' / 'spamhaus_live_state_verifier.py'
SERVICE = ROOT / 'deploy' / 'systemd' / 'wwcx-spamhaus-live-state.service'
TIMER = ROOT / 'deploy' / 'systemd' / 'wwcx-spamhaus-live-state.timer'
NETWORK_SERVICE = ROOT / 'deploy' / 'systemd' / 'wwcx-network-defense.service'
PAGE = ROOT / 'src' / 'web' / 'network-defense' / 'index.html'

installer = INSTALLER.read_text(encoding='utf-8')
verifier = VERIFIER.read_text(encoding='utf-8')
service = SERVICE.read_text(encoding='utf-8')
timer = TIMER.read_text(encoding='utf-8')
network_service = NETWORK_SERVICE.read_text(encoding='utf-8')
page = PAGE.read_text(encoding='utf-8')

required_installer = (
    'set -Eeuo pipefail',
    '55f053388cbe17b98ca1745c361b2d7b39f1a78f',
    'validate_spamhaus_live_state_verifier.py',
    'validate_spamhaus_live_state_deployer.py',
    'wwcx-spamhaus-live-state.service',
    'wwcx-spamhaus-live-state.timer',
    'wwcx-network-defense.service',
    'wwcx.spamhaus-live-state.v1',
    'traffic_controls_changed',
    'rollback',
    'The verifier made no nftables, firewall, DNS, routing, Fail2ban, proxy, or traffic-control changes.',
)
missing = [marker for marker in required_installer if marker not in installer]
if missing:
    raise SystemExit(f'Spamhaus live-state installer markers missing: {missing}')

required_verifier = (
    "'-j', 'list', 'table', TABLE_FAMILY, TABLE_NAME",
    "TABLE_NAME = 'bigbird_spamhaus'",
    "SCHEMA_VERSION = 'wwcx.spamhaus-live-state.v1'",
    "'set_elements_included': False",
    "'full_ruleset_included': False",
    "'raw_command_output_included': False",
    "'traffic_controls_changed': False",
)
missing = [marker for marker in required_verifier if marker not in verifier]
if missing:
    raise SystemExit(f'Spamhaus live-state verifier markers missing: {missing}')

for forbidden in (
    "'add'", "'delete'", "'flush'", "'insert'", "'replace'",
    "'-f'", 'os.system', 'shell=True',
):
    if forbidden in verifier:
        raise SystemExit(f'Verifier contains forbidden mutation marker: {forbidden}')

for forbidden in (
    'nft add', 'nft delete', 'nft flush', 'nft insert', 'nft replace',
    'suricata-update', 'unbound-control', 'iptables', 'ufw ',
    'systemctl restart bigbird-spamhaus-filter.service',
    'systemctl start bigbird-spamhaus-filter.service',
):
    if forbidden in installer:
        raise SystemExit(f'Installer contains forbidden control mutation: {forbidden}')

required_service = (
    'ExecStart=/usr/bin/python3 /opt/edge1-management-interface/server/spamhaus_live_state_verifier.py',
    'ReadWritePaths=/var/lib/bigbird-networking/spamhaus',
    'NoNewPrivileges=true',
    'ProtectSystem=strict',
    'RestrictAddressFamilies=AF_UNIX AF_NETLINK',
    'CapabilityBoundingSet=CAP_NET_ADMIN',
    'AmbientCapabilities=CAP_NET_ADMIN',
)
missing = [marker for marker in required_service if marker not in service]
if missing:
    raise SystemExit(f'Spamhaus live-state service hardening markers missing: {missing}')

for marker in ('OnUnitActiveSec=1min', 'Persistent=true', 'Unit=wwcx-spamhaus-live-state.service'):
    if marker not in timer:
        raise SystemExit(f'Spamhaus live-state timer marker missing: {marker}')

for marker in (
    'After=network-online.target',
    'Wants=network-online.target',
    'wwcx-spamhaus-live-state.service',
    'wwcx-fail2ban-live-state.service',
):
    if marker not in network_service:
        raise SystemExit(f'Network Defense verifier ordering marker missing: {marker}')

if 'Counts only dedicated sanitized live-state verifiers.' not in page:
    raise SystemExit('Network Defense page does not explain verified-enforcement counting')

print('Spamhaus live-state deployment validation passed')
