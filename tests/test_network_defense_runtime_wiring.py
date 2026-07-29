#!/usr/bin/env python3
"""Verify Network Defense uses the DNS-aware runtime path."""

import unittest
from pathlib import Path


class NetworkDefenseRuntimeWiringTests(unittest.TestCase):
    def test_systemd_uses_dns_exporter(self):
        service = Path('deploy/systemd/wwcx-network-defense.service').read_text(encoding='utf-8')
        self.assertIn('server/network_defense_dns_exporter.py', service)
        self.assertNotIn('server/network_defense_exporter.py', service)

    def test_optional_telemetry_paths_do_not_block_startup(self):
        service = Path('deploy/systemd/wwcx-network-defense.service').read_text(encoding='utf-8')
        self.assertIn('ReadOnlyPaths=-/var/lib/bigbird/operations-center -/var/lib/bigbird-networking', service)
        self.assertNotIn('ReadOnlyPaths=/var/lib/bigbird/operations-center', service)

    def test_runtime_writes_only_to_scoped_publication_directory(self):
        service = Path('deploy/systemd/wwcx-network-defense.service').read_text(encoding='utf-8')
        scoped = '/var/www/edge1-status/network-defense/data'
        self.assertIn(f'--output {scoped}/network-defense.json', service)
        self.assertIn(f'ReadWritePaths={scoped}', service)
        self.assertNotIn('ReadWritePaths=/var/www/edge1-status\n', service)
        self.assertIn('CapabilityBoundingSet=\n', service)

    def test_network_console_mentions_dns_readiness(self):
        page = Path('src/web/network-defense/index.html').read_text(encoding='utf-8')
        self.assertIn('DNS policy readiness', page)
        self.assertIn('staged policy evidence', page)
        self.assertIn('traffic_controls_changed:false', page)


if __name__ == '__main__':
    unittest.main()
