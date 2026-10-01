#!/usr/bin/env python3
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TransparentControlCenterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shell = (ROOT / "src/web/operator-shell/shell.js").read_text(encoding="utf-8")
        cls.contacts = (ROOT / "src/web/contacts/index.html").read_text(encoding="utf-8")

    def test_shell_home_and_fallback_stay_authenticated(self):
        self.assertIn('brand.href = "/edge1-ops/security/"', self.shell)
        self.assertIn('escape.href = "/edge1-ops/status/"', self.shell)
        self.assertNotIn('escape.href = "/edge1-status/"', self.shell)

    def test_shell_preserves_orientation(self):
        self.assertIn('"Edge1 / " + activeModule.section + " / " + activeModule.label', self.shell)
        self.assertIn("window.location.pathname", self.shell)
        self.assertIn('link.setAttribute("aria-current", "page")', self.shell)

    def test_contacts_has_one_global_navigation_system(self):
        self.assertIn('data-module="contacts-relationships"', self.contacts)
        self.assertIn('/edge1-ops/status/operator-shell/shell.js', self.contacts)
        self.assertNotIn('class="module-nav"', self.contacts)
        self.assertNotIn('EDGE1_INTELLIGENCE_NAV_START', self.contacts)


if __name__ == "__main__":
    unittest.main()
