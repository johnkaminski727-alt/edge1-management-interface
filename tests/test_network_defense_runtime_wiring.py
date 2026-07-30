#!/usr/bin/env python3
"""Verify Network Defense uses the DNS-, Spamhaus-, Fail2ban-, and nftables-aware runtime path."""

import unittest
from pathlib import Path


class NetworkDefenseRuntimeWiringTests(unittest.TestCase):
    def test_systemd_uses_nftables_aware_exporter(self):
        service = Path('deploy/systemd/wwcx-network-defense.service').read_text(encoding='utf-8')
        self.assertIn('server/network_defense_nftables_exporter.py', service)
        self.assertNotIn('server/network_defense_fail2ban_exporter.py --output', service)
        self.assertNotIn('server/network_defense_dns_exporter.py --output', service)
        self.assertNotIn('server/network_defense_exporter.py --output', service)

    def test_network_defense_orders_after_dedicated_verifiers(self):
        service = Path('deploy/systemd/wwcx-network-defense.service').read_text(encoding='utf-8')
        for verifier in (
            'wwcx-spamhaus-live-state.service',
            'wwcx-fail2ban-live-state.service',
            'wwcx-nftables-live-state.service',
        ):
            self.assertIn(verifier, service)
        self.assertIn(
            'Wants=network-online.target wwcx-spamhaus-live-state.service wwcx-fail2ban-live-state.service wwcx-nftables-live-state.service',
            service,
        )

    def test_optional_telemetry_paths_do_not_block_startup(self):
        service = Path('deploy/systemd/wwcx-network-defense.service').read_text(encoding='utf-8')
        self.assertIn(
            'ReadOnlyPaths=-/var/lib/bigbird/operations-center -/var/lib/bigbird-networking -/var/lib/bigbird-security',
            service,
        )
        self.assertNotIn('ReadOnlyPaths=/var/lib/bigbird/operations-center', service)

    def test_runtime_writes_only_to_scoped_publication_directory(self):
        service = Path('deploy/systemd/wwcx-network-defense.service').read_text(encoding='utf-8')
        scoped = '/var/www/edge1-status/network-defense/data'
        self.assertIn(f'--output {scoped}/network-defense.json', service)
        self.assertIn(f'ReadWritePaths={scoped}', service)
        self.assertNotIn('ReadWritePaths=/var/www/edge1-status\n', service)
        self.assertIn('CapabilityBoundingSet=\n', service)
        self.assertIn('AmbientCapabilities=\n', service)
        self.assertNotIn('CAP_NET_ADMIN', service)

    def test_fail2ban_verifier_has_no_capabilities_or_network_access(self):
        service = Path('deploy/systemd/wwcx-fail2ban-live-state.service').read_text(encoding='utf-8')
        self.assertIn('User=root', service)
        self.assertIn('RestrictAddressFamilies=AF_UNIX', service)
        self.assertIn('CapabilityBoundingSet=\n', service)
        self.assertIn('AmbientCapabilities=\n', service)
        self.assertNotIn('CAP_NET_ADMIN', service)
        self.assertNotIn('AF_INET', service)

    def test_nftables_verifier_has_only_read_capability_and_netlink(self):
        service = Path('deploy/systemd/wwcx-nftables-live-state.service').read_text(encoding='utf-8')
        self.assertIn('User=root', service)
        self.assertIn('RestrictAddressFamilies=AF_UNIX AF_NETLINK', service)
        self.assertIn('CapabilityBoundingSet=CAP_NET_ADMIN', service)
        self.assertIn('AmbientCapabilities=CAP_NET_ADMIN', service)
        self.assertNotIn('CAP_NET_RAW', service)
        self.assertNotIn('AF_INET', service)

    def test_network_console_mentions_dns_and_verifier_boundaries(self):
        page = Path('src/web/network-defense/index.html').read_text(encoding='utf-8')
        page_lower = page.lower()
        self.assertIn('dns policy readiness', page_lower)
        self.assertIn('staged policy evidence', page_lower)
        self.assertIn('traffic_controls_changed:false', page)
        self.assertIn('Counts only dedicated sanitized live-state verifiers.', page)


if __name__ == '__main__':
    unittest.main()
