#!/usr/bin/env python3
import pathlib
import unittest

ROOT = pathlib.Path(__file__).parents[1]
INSTALLER = ROOT / 'deploy' / 'install-fail2ban-live-state-observability.sh'
SERVICE = ROOT / 'deploy' / 'systemd' / 'wwcx-fail2ban-live-state.service'
TIMER = ROOT / 'deploy' / 'systemd' / 'wwcx-fail2ban-live-state.timer'
NETWORK = ROOT / 'deploy' / 'systemd' / 'wwcx-network-defense.service'
VERIFIER = ROOT / 'server' / 'fail2ban_live_state_verifier.py'
WRAPPER = ROOT / 'server' / 'network_defense_fail2ban_exporter.py'
FINAL_WRAPPER = ROOT / 'server' / 'network_defense_nftables_exporter.py'


class Fail2banLiveStateDeployerTests(unittest.TestCase):
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
        self.assertIn('/var/lib/wwcx-deployment-evidence/fail2ban-live-state', script)

    def test_installer_never_mutates_fail2ban_or_traffic_controls(self):
        script = INSTALLER.read_text(encoding='utf-8')
        forbidden = (
            'systemctl start fail2ban',
            'systemctl restart fail2ban',
            'systemctl reload fail2ban',
            'systemctl stop fail2ban',
            'fail2ban-client set',
            'fail2ban-client start',
            'fail2ban-client stop',
            'fail2ban-client reload',
            'fail2ban-client unbanip',
            'fail2ban-client banip',
            'nft add',
            'nft delete',
            'nft flush',
            'iptables ',
            'ip6tables ',
            'unbound-control reload',
        )
        lowered = script.lower()
        for command in forbidden:
            self.assertNotIn(command, lowered)

    def test_verifier_service_is_root_but_capability_free(self):
        unit = SERVICE.read_text(encoding='utf-8')
        self.assertIn('User=root', unit)
        self.assertIn('Environment=LC_ALL=C', unit)
        self.assertIn('ProtectSystem=strict', unit)
        self.assertIn('RestrictAddressFamilies=AF_UNIX', unit)
        self.assertIn('ReadWritePaths=/var/lib/bigbird-security/fail2ban', unit)
        self.assertIn('CapabilityBoundingSet=\n', unit)
        self.assertIn('AmbientCapabilities=\n', unit)
        self.assertNotIn('CAP_NET_ADMIN', unit)
        self.assertNotIn('AF_INET', unit)

    def test_timer_and_network_ordering_are_explicit(self):
        timer = TIMER.read_text(encoding='utf-8')
        network = NETWORK.read_text(encoding='utf-8')
        final_wrapper = FINAL_WRAPPER.read_text(encoding='utf-8')
        self.assertIn('OnUnitActiveSec=60s', timer)
        self.assertIn('wwcx-fail2ban-live-state.service', network)
        self.assertIn('wwcx-nftables-live-state.service', network)
        self.assertIn('server/network_defense_nftables_exporter.py', network)
        self.assertIn('network_defense_fail2ban_exporter.py', final_wrapper)
        self.assertIn('-/var/lib/bigbird-security', network)
        self.assertIn('CapabilityBoundingSet=\n', network)

    def test_privacy_and_non_enforcement_markers_are_present(self):
        verifier = VERIFIER.read_text(encoding='utf-8')
        wrapper = WRAPPER.read_text(encoding='utf-8')
        for marker in (
            "'banned_addresses_included': False",
            "'raw_client_output_included': False",
            "'commands_included': False",
            "'enforcement_verified': False",
            "'traffic_controls_changed': False",
        ):
            self.assertIn(marker, verifier)
        self.assertIn("'fail2ban_banned_addresses_included'] = False", wrapper)
        self.assertIn("'fail2ban_raw_client_output_included'] = False", wrapper)
        self.assertIn("'enforcement_verified') is not False", wrapper)

    def test_installer_accepts_truthful_non_mutating_states(self):
        script = INSTALLER.read_text(encoding='utf-8')
        for state in ('active_observed', 'partial', 'inactive', 'not_installed', 'unavailable'):
            self.assertIn(state, script)
        self.assertIn("assert component['enforcement_verified'] is False", script)


if __name__ == '__main__':
    unittest.main()
