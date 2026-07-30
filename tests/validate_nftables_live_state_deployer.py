#!/usr/bin/env python3
import pathlib
import unittest

ROOT = pathlib.Path(__file__).parents[1]
INSTALLER = ROOT / 'deploy' / 'install-nftables-live-state-observability.sh'
SERVICE = ROOT / 'deploy' / 'systemd' / 'wwcx-nftables-live-state.service'
TIMER = ROOT / 'deploy' / 'systemd' / 'wwcx-nftables-live-state.timer'
NETWORK = ROOT / 'deploy' / 'systemd' / 'wwcx-network-defense.service'
VERIFIER = ROOT / 'server' / 'nftables_live_state_verifier.py'
WRAPPER = ROOT / 'server' / 'network_defense_nftables_exporter.py'


class NftablesLiveStateDeployerTests(unittest.TestCase):
    def test_installer_is_rollback_safe_and_evidence_bounded(self):
        script = INSTALLER.read_text(encoding='utf-8')
        for marker in (
            'set -Eeuo pipefail',
            'trap rollback ERR INT TERM',
            'backup_path',
            'restore_path',
            'acceptance-summary.json',
            'traffic_controls_changed=false',
            'systemctl enable --now "$TIMER"',
        ):
            self.assertIn(marker, script)
        self.assertIn('/var/lib/wwcx-deployment-evidence/nftables-live-state', script)

    def test_installer_never_mutates_firewall_or_other_controls(self):
        script = INSTALLER.read_text(encoding='utf-8').lower()
        forbidden = (
            'nft add', 'nft delete', 'nft flush', 'nft insert', 'nft replace',
            'nft -f', 'nft --file', 'iptables ', 'ip6tables ', 'firewall-cmd', 'ufw ',
            'systemctl start nftables.service', 'systemctl restart nftables.service',
            'systemctl reload nftables.service', 'systemctl stop nftables.service',
            'systemctl try-restart nftables.service',
            'fail2ban-client set', 'unbound-control reload', 'suricata-update',
        )
        for command in forbidden:
            self.assertNotIn(command, script)

    def test_verifier_service_has_only_required_read_capability(self):
        unit = SERVICE.read_text(encoding='utf-8')
        self.assertIn('User=root', unit)
        self.assertIn('ProtectSystem=strict', unit)
        self.assertIn('RestrictAddressFamilies=AF_UNIX AF_NETLINK', unit)
        self.assertIn('ReadWritePaths=/var/lib/bigbird-networking/nftables', unit)
        self.assertIn('CapabilityBoundingSet=CAP_NET_ADMIN', unit)
        self.assertIn('AmbientCapabilities=CAP_NET_ADMIN', unit)
        self.assertNotIn('CAP_NET_RAW', unit)
        self.assertNotIn('AF_INET', unit)

    def test_network_defense_remains_capability_free_and_layered(self):
        unit = NETWORK.read_text(encoding='utf-8')
        wrapper = WRAPPER.read_text(encoding='utf-8')
        self.assertIn('wwcx-nftables-live-state.service', unit)
        self.assertIn('server/network_defense_nftables_exporter.py', unit)
        self.assertIn('network_defense_fail2ban_exporter.py', wrapper)
        self.assertIn('CapabilityBoundingSet=\n', unit)
        self.assertIn('AmbientCapabilities=\n', unit)
        self.assertNotIn('CAP_NET_ADMIN', unit)

    def test_timer_and_private_snapshot_modes_are_explicit(self):
        timer = TIMER.read_text(encoding='utf-8')
        verifier = VERIFIER.read_text(encoding='utf-8')
        installer = INSTALLER.read_text(encoding='utf-8')
        self.assertIn('OnUnitActiveSec=60s', timer)
        self.assertIn('Persistent=true', timer)
        self.assertIn('Unit=wwcx-nftables-live-state.service', timer)
        self.assertIn('os.chmod(temporary, 0o640)', verifier)
        self.assertIn('install -d -o root -g root -m 0750 "$STATE_ROOT"', installer)
        self.assertIn('stat.S_IMODE(source.stat().st_mode) == 0o640', installer)

    def test_privacy_and_non_enforcement_markers_are_present(self):
        verifier = VERIFIER.read_text(encoding='utf-8')
        wrapper = WRAPPER.read_text(encoding='utf-8')
        for marker in (
            "'addresses_included': False",
            "'table_names_included': False",
            "'set_elements_included': False",
            "'rule_expressions_included': False",
            "'rule_comments_included': False",
            "'rule_handles_included': False",
            "'full_ruleset_included': False",
            "'enforcement_verified': False",
            "'traffic_controls_changed': False",
        ):
            self.assertIn(marker, verifier)
        self.assertIn("privacy['firewall_addresses_included'] = False", wrapper)
        self.assertIn("privacy['firewall_names_included'] = False", wrapper)
        self.assertIn("privacy['firewall_rule_expressions_included'] = False", wrapper)
        self.assertIn("observation.get('enforcement_verified') is not False", wrapper)

    def test_installer_accepts_truthful_observation_states(self):
        script = INSTALLER.read_text(encoding='utf-8')
        for state in ('ruleset_observed', 'partial', 'empty', 'not_installed', 'unavailable'):
            self.assertIn(state, script)
        self.assertIn("assert component['enforcement_verified'] is False", script)
        self.assertIn("assert defense['summary']['verified_enforcement_count']", script)


if __name__ == '__main__':
    unittest.main()
