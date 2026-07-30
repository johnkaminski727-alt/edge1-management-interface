#!/usr/bin/env python3
"""Repository validation for the four authorized Edge1 security completion programs."""
from __future__ import annotations
import importlib.util
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNTIME_POLICY = ROOT / "config/security/suricata-protected-retention-runtime.json"
AUTHORIZATION = ROOT / "config/security/edge1-security-completion-authorization.json"
RETENTION = ROOT / "server/suricata_protected_retention.py"
RETENTION_SERVICE = ROOT / "deploy/systemd/wwcx-suricata-protected-retention.service"
RETENTION_TIMER = ROOT / "deploy/systemd/wwcx-suricata-protected-retention.timer"
PUBLIC_SERVICE = ROOT / "deploy/systemd/wwcx-edge1-minimized-public-summary.service"
PUBLIC_TIMER = ROOT / "deploy/systemd/wwcx-edge1-minimized-public-summary.timer"
STAGE = ROOT / "deploy/stage-edge1-public-boundary.sh"
CUTOVER = ROOT / "deploy/cutover-edge1-public-boundary.sh"
STAGE_CONF = ROOT / "deploy/apache/edge1-security-boundary-stage.conf.in"
CUTOVER_CONF = ROOT / "deploy/apache/edge1-security-boundary-cutover.conf.in"
LOGIN = ROOT / "src/web/edge1-login/index.html"

class CompletionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy=json.loads(RUNTIME_POLICY.read_text())
        cls.authorization=json.loads(AUTHORIZATION.read_text())
        cls.retention=RETENTION.read_text()
        cls.retention_service=RETENTION_SERVICE.read_text()
        cls.retention_timer=RETENTION_TIMER.read_text()
        cls.public_service=PUBLIC_SERVICE.read_text()
        cls.public_timer=PUBLIC_TIMER.read_text()
        cls.stage=STAGE.read_text()
        cls.cutover=CUTOVER.read_text()
        cls.stage_conf=STAGE_CONF.read_text()
        cls.cutover_conf=CUTOVER_CONF.read_text()
        cls.login=LOGIN.read_text()

    def test_authorization_is_exact_and_guarded(self):
        self.assertEqual(self.authorization['contract'], 'wwcx.edge1-security-completion-authorization.v1')
        self.assertTrue(all(self.authorization['programs'].values()))
        guard=self.authorization['guardrails']
        self.assertFalse(guard['dns_enforcement_change'])
        self.assertFalse(guard['traffic_control_change'])
        self.assertFalse(guard['new_public_listener'])
        self.assertFalse(guard['retained_data_deletion'])
        self.assertTrue(guard['archive_before_withdrawal'])
        self.assertTrue(guard['authenticated_equivalence_before_cutover'])

    def test_runtime_policy_preserves_design_limits(self):
        p=self.policy
        self.assertEqual(p['status'], 'implementation_ready')
        self.assertTrue(p['enabled'])
        self.assertTrue(p['acceptance']['deployment_authorized'])
        self.assertEqual(p['ingest']['source'], '/var/lib/bigbird/operations-center/latest.json')
        self.assertFalse(p['ingest']['raw_eve_allowed'])
        self.assertEqual(p['storage']['retention_days'], 30)
        self.assertEqual(p['storage']['max_database_bytes'], 256*1024*1024)
        self.assertEqual(p['storage']['max_events'], 100000)
        self.assertEqual(p['storage']['page_size_bytes']*p['storage']['max_page_count'], p['storage']['max_database_bytes'])
        self.assertEqual(p['storage']['directory_mode'], '0700')
        self.assertEqual(p['storage']['database_mode'], '0600')
        self.assertFalse(p['query']['network_listener'])
        self.assertFalse(p['query']['public_endpoint'])
        self.assertTrue(p['rollback']['preserve_database_by_default'])

    def test_retention_runtime_has_privacy_integrity_and_bounded_pruning(self):
        for marker in ('PRAGMA quick_check','PRAGMA max_page_count','PRAGMA incremental_vacuum','INSERT OR IGNORE','os.replace','fcntl.LOCK_EX'):
            self.assertIn(marker, self.retention)
        self.assertNotIn('/var/log/suricata/eve.json', self.retention)
        self.assertNotIn('/var/www', self.retention)
        self.assertIn('RestrictAddressFamilies=AF_UNIX', self.retention_service)
        self.assertIn('CapabilityBoundingSet=', self.retention_service)
        self.assertIn('ReadWritePaths=/var/lib/bigbird-security/suricata-history', self.retention_service)
        self.assertIn('OnUnitActiveSec=120s', self.retention_timer)

    def test_public_exporter_runtime_has_no_new_listener(self):
        self.assertIn('RestrictAddressFamilies=AF_UNIX', self.public_service)
        self.assertIn('CapabilityBoundingSet=', self.public_service)
        self.assertIn('/var/lib/bigbird-public-status/www/status.json', self.public_service)
        self.assertIn('OnUnitActiveSec=120s', self.public_timer)

    def test_authenticated_stage_is_fail_closed_audited_and_secret_free(self):
        for marker in ('AuthType form','AuthFormProvider file','AuthUserFile "@@AUTH_USER_FILE@@"','SessionCookieName edge1_ops_session','httponly;secure;samesite=Strict','SessionCryptoPassphraseFile','Require valid-user','Options -Indexes','SetOutputFilter RATE_LIMIT','SetEnv rate-limit 512','CustomLog /var/log/apache2/edge1-ops-access.log'):
            self.assertIn(marker, self.stage_conf)
        for forbidden in ('password=', 'token=', 'secret=', 'BEGIN PRIVATE KEY'):
            self.assertNotIn(forbidden, self.stage_conf.lower())
        self.assertIn('name="httpd_username"', self.login)
        self.assertIn('name="httpd_password"', self.login)
        self.assertIn('form_acceptance', self.stage)
        self.assertIn('anonymous detailed route did not fail closed', self.stage)

    def test_cutover_orders_auth_archive_and_public_withdrawal(self):
        auth=self.cutover.index('login_check\n# Authentication succeeds before any anonymous route is withdrawn.')
        archive=self.cutover.index('detailed-public-archive.tar.gz')
        mutation=self.cutover.index('install -o root -g root -m 0644 "$CUTOVER_COPY" "$CONF"')
        self.assertLess(auth, archive)
        self.assertLess(archive, mutation)
        self.assertIn('detailed_artifacts_deleted=false', self.cutover)
        self.assertIn('returned HTTP $code instead of 404', self.cutover)
        self.assertIn('Alias "/edge1-status/public/status.json"', self.cutover_conf)
        self.assertIn('Alias "/edge1-status/" "/var/lib/bigbird-public-status/www/"', self.cutover_conf)
        self.assertIn('Alias "/edge1-ops/" "/var/www/edge1-status/"', self.cutover_conf)
        self.assertIn('Header always unset Access-Control-Allow-Origin', self.cutover_conf)

    def test_deployment_scripts_preserve_control_planes_and_evidence(self):
        retention_deploy=(ROOT/'deploy/activate-suricata-protected-retention.sh').read_text()
        for marker in ('suricata-before.txt','suricata-after.txt','network-defense-timer-before.txt','nftables-before.sha256','listeners-before.txt','manifest.sha256','rolled_back'):
            self.assertIn(marker, retention_deploy)
        self.assertNotIn('systemctl restart suricata', retention_deploy)
        self.assertNotIn('nft add', retention_deploy)
        self.assertNotIn('unbound', retention_deploy.lower())


def load_tests(loader, tests, pattern):
    spec=importlib.util.spec_from_file_location('retention_runtime_tests', ROOT/'tests/test_suricata_protected_retention_runtime.py')
    module=importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return unittest.TestSuite([tests, loader.loadTestsFromModule(module)])

if __name__ == '__main__':
    unittest.main()
