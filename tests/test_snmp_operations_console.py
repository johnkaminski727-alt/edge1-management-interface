from __future__ import annotations

import unittest
from pathlib import Path


class SnmpOperationsConsoleStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path("src/web/operations-center/snmp.html").read_text(encoding="utf-8")
        cls.publisher = Path("deploy/operations-center/publish.sh").read_text(encoding="utf-8")
        cls.apache_noindex = Path(
            "deploy/apache/edge1-status-operations-center-no-index.conf"
        ).read_text(encoding="utf-8")

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

    def test_back_link_returns_to_published_operations_center(self):
        self.assertIn('href="/edge1-status/">Back to Operations Center</a>', self.source)
        self.assertNotIn('href="/edge1-status/operations-center/">Back to Operations Center</a>', self.source)

    def test_public_snmp_handoff_directory_disables_autoindex(self):
        self.assertIn(
            '<Directory "/var/www/edge1-status/operations-center">',
            self.apache_noindex,
        )
        self.assertIn("Options -Indexes", self.apache_noindex)
        self.assertNotIn("Options Indexes", self.apache_noindex)

    def test_dangerous_controls_are_absent(self):
        self.assertIn("SNMP SET: <strong>Disabled by policy</strong>", self.source)
        self.assertNotIn("/traps", self.source)
        self.assertNotIn("subprocess", self.source)
        self.assertNotIn("/bin/sh", self.source)

    def test_public_publisher_does_not_publish_full_console(self):
        self.assertNotIn('install -m 0644 "$SNMP_SOURCE" "$SNMP_DEST"', self.publisher)
        self.assertIn("Open authenticated SNMP Operations", self.publisher)
        self.assertIn("/edge1-ops/snmp/", self.publisher)

    def test_topology_uses_backend_schema_and_evidence(self):
        self.assertIn("local_device_id", self.source)
        self.assertIn("remote_device_id", self.source)
        self.assertIn("evidence_json", self.source)
        self.assertIn("data-link", self.source)
        self.assertIn("No topology evidence yet", self.source)

    def test_discovery_completes_explicit_v3_onboarding(self):
        self.assertIn("snmp_version", self.source)
        self.assertIn("data-onboard", self.source)
        self.assertIn("api('/devices'", self.source)
        self.assertIn("Legacy SNMP onboarding requires a separate explicit approval path", self.source)
        self.assertNotIn("legacy_protocol_approved:true", self.source)

    def test_degraded_auth_and_ai_fallback_states_are_explicit(self):
        self.assertIn("AUTH REQUIRED", self.source)
        self.assertIn("ACCESS DENIED", self.source)
        self.assertIn("DEGRADED", self.source)
        self.assertIn("deterministic_evidence", self.source)
        self.assertIn("unavailable - deterministic fallback", self.source)

    def test_numeric_if_mib_states_and_telemetry_charts_are_supported(self):
        self.assertIn("const ifStatus", self.source)
        self.assertIn("2:'down'", self.source)
        self.assertIn("function metricCharts", self.source)
        self.assertIn("Telemetry trends", self.source)


if __name__ == "__main__":
    unittest.main()
