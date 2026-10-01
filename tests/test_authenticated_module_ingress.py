#!/usr/bin/env python3
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "deploy/operations-center/install-authenticated-status-route.sh"
REGISTRY = ROOT / "config/edge1_operator/navigation_registry.json"
THEME = ROOT / "src/web/operator-shell/theme.css"


class AuthenticatedModuleIngressTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.installer = INSTALLER.read_text(encoding="utf-8")
        cls.registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        cls.theme = THEME.read_text(encoding="utf-8")

    def test_ingress_requires_existing_edge1_session(self):
        for token in (
            "location ^~ /edge1-ops/status/",
            "auth_request /_edge1_status_session_check;",
            "proxy_pass http://127.0.0.1:8108/edge1-ops/session;",
            "proxy_set_header Cookie $http_cookie;",
            "internal;",
            "alias /var/www/edge1-status/;",
        ):
            self.assertIn(token, self.installer)

    def test_ingress_has_backup_and_rollback(self):
        for token in (
            "/var/backups/edge1-authenticated-status-",
            "edge1-private.conf.before",
            "rollback.sh",
            "nginx -t",
            "systemctl reload nginx.service",
        ):
            self.assertIn(token, self.installer)

    def test_live_registry_routes_stay_inside_cookie_namespace(self):
        live = [
            item for item in self.registry["modules"]
            if item.get("availability") == "accepted_live"
        ]
        self.assertEqual(len(live), 4)
        for item in live:
            self.assertTrue(item["browser_route"].startswith("/edge1-ops/status/"))
            self.assertEqual(item["authorization"], "authenticated_edge1_session")

    def test_contacts_style_tokens_are_shared(self):
        for token in (
            "--edge1-page:#f4f7fb",
            "--edge1-panel:#ffffff",
            "--edge1-blue:#1768a5",
            "--edge1-text:#172337",
        ):
            self.assertIn(token, self.theme)


if __name__ == "__main__":
    unittest.main()
