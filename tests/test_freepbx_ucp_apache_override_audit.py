from __future__ import annotations

import importlib.util
import json
import pathlib
import re
import stat
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/security/audit_freepbx_ucp_apache_overrides.py"
POLICY = ROOT / "config/security/freepbx-ucp-apache-override-audit-policy.json"

spec = importlib.util.spec_from_file_location("freepbx_override_audit", SCRIPT)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FreePbxOverrideAuditTests(unittest.TestCase):
    def test_policy_is_read_only_and_fail_closed(self):
        value = json.loads(POLICY.read_text(encoding="utf-8"))
        self.assertEqual(value["contract"], "wwcx.freepbx-ucp-apache-override-audit-policy.v1")
        self.assertTrue(value["execution_authorized"])
        guard = value["guardrails"]
        self.assertTrue(guard["read_only_host_inspection"])
        self.assertTrue(guard["evidence_writes_only"])
        for key in (
            "follow_symlinks",
            "record_htaccess_values",
            "record_secret_directive_values",
            "record_authentication_material",
            "record_cookie_values",
            "record_environment",
            "apache_configuration_change",
            "service_reload_or_restart",
            "module_or_site_enablement",
            "route_or_authentication_change",
            "listener_or_firewall_change",
            "production_traffic_change",
        ):
            self.assertFalse(guard[key], key)
        self.assertTrue(value["acceptance"]["manual_effective_policy_review_required"])
        self.assertFalse(value["acceptance"]["mutation_performed"])

    def test_parser_records_directory_context_and_override_value_only(self):
        fixture = """
DocumentRoot /var/www/html
<Directory "/var/www/html">
    AllowOverride None
</Directory>
<Directory "/var/www/html/ucp">
    AllowOverride AuthConfig FileInfo
    AuthUserFile /root/never-record-this
</Directory>
"""
        value = module.parse_apache_config_text(pathlib.Path("freepbx.conf"), fixture)
        self.assertEqual(value["document_roots"][0]["path"], "/var/www/html")
        self.assertEqual(
            [(item["context_path"], item["value"]) for item in value["allowoverride_occurrences"]],
            [
                ("/var/www/html", "None"),
                ("/var/www/html/ucp", "AuthConfig FileInfo"),
            ],
        )
        encoded = json.dumps(value)
        self.assertNotIn("never-record-this", encoded)
        self.assertNotIn("AuthUserFile", encoded)

    def test_htaccess_inventory_never_records_directive_values(self):
        payload = b"""# FreePBX UCP rules
AuthUserFile /root/sensitive/passwords
RewriteEngine On
RewriteRule ^ secret-target [L]
SetEnv CLIENT_SECRET should-not-escape
"""
        value = module.inspect_htaccess_bytes(
            pathlib.Path("/var/www/html/ucp/.htaccess"), payload, stat.S_IFREG | 0o640
        )
        self.assertEqual(value["mode"], "0640")
        self.assertIn("authuserfile", value["directive_names"])
        self.assertIn("authuserfile", value["secret_bearing_directive_names"])
        self.assertFalse(value["directive_values_recorded"])
        encoded = json.dumps(value)
        for forbidden in ("passwords", "secret-target", "should-not-escape", "CLIENT_SECRET"):
            self.assertNotIn(forbidden, encoded)

    def test_fallback_redactor_removes_headers_assignments_and_url_userinfo(self):
        sample = (
            "Authorization: Bearer abc.def.ghi\n"
            "Cookie: session=abcdef\n"
            "CLIENT_SECRET=hunter2\n"
            "proxy=https://alice:password@example.invalid/path\n"
        )
        result = module.sanitize_fallback(sample)
        for forbidden in ("abc.def.ghi", "abcdef", "hunter2", "alice:password"):
            self.assertNotIn(forbidden, result)
        self.assertGreaterEqual(result.count("<redacted>"), 4)

    def test_source_contains_only_read_only_apache_commands(self):
        text = SCRIPT.read_text(encoding="utf-8")
        for marker in (
            '"-t"',
            '"-S"',
            '"-M"',
            '"DUMP_RUN_CFG"',
            '"mutation_performed": False',
            '"apache_configuration_changed": False',
            '"service_reloaded_or_restarted": False',
            '"htaccess_values_recorded": False',
            '"authentication_material_recorded": False',
            'sha256-manifest.txt',
        ):
            self.assertIn(marker, text)
        for pattern in (
            r"systemctl\s+(start|stop|restart|reload|enable|disable|mask|unmask)",
            r"\b(a2enmod|a2dismod|a2enconf|a2disconf|a2ensite|a2dissite)\b",
            r"\b(apache2ctl|apachectl|httpd)\s+(graceful|restart|stop|start)",
            r"\b(nft|iptables|ip6tables|ufw|firewall-cmd)\b",
            r"subprocess\.run\([^\)]*shell\s*=\s*True",
            r"os\.environ",
            r"printenv",
        ):
            self.assertIsNone(re.search(pattern, text), pattern)

    def test_approved_candidate_roots_remain_bounded(self):
        configured = [pathlib.Path("/var/www/html"), pathlib.Path("/usr/share/freepbx")]
        self.assertEqual(
            module.approved_candidate_root("/var/www/html/ucp", configured),
            pathlib.Path("/var/www/html/ucp"),
        )
        self.assertIsNone(module.approved_candidate_root("/etc", configured))
        self.assertIsNone(module.approved_candidate_root("${APACHE_DOCUMENT_ROOT}", configured))


if __name__ == "__main__":
    unittest.main()
