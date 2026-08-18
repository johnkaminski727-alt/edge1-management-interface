from __future__ import annotations

import unittest
from pathlib import Path


class SnmpOperationsConsoleStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path("src/web/operations-center/snmp.html").read_text(encoding="utf-8")
        cls.publisher = Path("deploy/operations-center/publish.sh").read_text(encoding="utf-8")

    def test_same_origin_authenticated_adapter_is_used(self):
        self.assertIn("/edge1-ops/api/v1/snmp", self.source)
        self.assertNotIn("http://127.0.0.1:8112", self.source)
        self.assertNotIn("X-WWCX-Signature", self.source)

    def test_browser_does_not_reference_secret_material(self):
        for marker in (
            "/etc/edge1-snmp/api.secret", "BB_RELAY_SECRET", "BB_RELAY_KEY_ID",
            "OPENAI_API_KEY", "localStorage", "sessionStorage",
        ):
            self.assertNotIn(marker, self.source)

    def test_csp_template_shape_is_stable(self):
        self.assertEqual(self.source.count("<style>"), 1)
        self.assertEqual(self.source.count("<script>"), 1)

    def test_required_operator_sections_exist(self):
        for section in (
            "overview", "devices", "interfaces", "alerts", "incidents", "topology",
            "events", "ai", "discovery", "mibs", "actions", "audit", "settings",
        ):
            self.assertIn(f'data-view="{section}"', self.source)

    def test_dangerous_controls_are_absent(self):
        self.assertIn("SNMP SET: <strong>Disabled by policy</strong>", self.source)
        self.assertNotIn("/traps", self.source)
        self.assertNotIn("subprocess", self.source)
        self.assertNotIn("/bin/sh", self.source)

    def test_public_publisher_does_not_publish_full_console(self):
        self.assertNotIn('install -m 0644 "$SNMP_SOURCE" "$SNMP_DEST"', self.publisher)
        self.assertIn("Open authenticated SNMP Operations", self.publisher)
        self.assertIn("/edge1-ops/snmp/", self.publisher)


if __name__ == "__main__":
    unittest.main()
