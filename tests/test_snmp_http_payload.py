from __future__ import annotations

import unittest

from server.edge1_security_auth_http_snmp import normalize_snmp_browser_payload


class SnmpBrowserPayloadTests(unittest.TestCase):
    def test_discovery_rejects_legacy_approval_and_unknown_fields(self):
        good = normalize_snmp_browser_payload("/api/snmp/discovery", {
            "cidr": "10.0.0.0/30",
            "credential_reference": "router-v3",
            "dry_run": True,
            "concurrency": 8,
        })
        self.assertEqual(good["concurrency"], 8)
        with self.assertRaises(ValueError):
            normalize_snmp_browser_payload("/api/snmp/discovery", {
                "cidr": "10.0.0.0/30",
                "credential_reference": "legacy",
                "legacy_protocol_approved": True,
            })
        with self.assertRaises(ValueError):
            normalize_snmp_browser_payload("/api/snmp/discovery", {
                "cidr": "10.0.0.0/30",
                "credential_reference": "router-v3",
                "concurrency": 1000,
            })

    def test_device_browser_path_is_v3_only_and_cannot_enable_writes(self):
        good = normalize_snmp_browser_payload("/api/snmp/devices", {
            "display_name": "router",
            "management_address": "10.0.0.1",
            "snmp_version": "3",
            "credential_reference": "router-v3",
        })
        self.assertEqual(good["snmp_version"], "3")
        with self.assertRaises(ValueError):
            normalize_snmp_browser_payload("/api/snmp/devices", {
                "management_address": "10.0.0.1",
                "snmp_version": "2c",
                "credential_reference": "legacy",
            })
        with self.assertRaises(ValueError):
            normalize_snmp_browser_payload("/api/snmp/devices", {
                "management_address": "10.0.0.1",
                "snmp_version": "3",
                "credential_reference": "router-v3",
                "write_enabled": True,
            })

    def test_mib_import_cannot_supply_arbitrary_directories(self):
        self.assertEqual(
            normalize_snmp_browser_payload("/api/snmp/mibs/import", {"module": "IF-MIB"}),
            {"module": "IF-MIB"},
        )
        with self.assertRaises(ValueError):
            normalize_snmp_browser_payload("/api/snmp/mibs/import", {
                "module": "IF-MIB", "mib_dirs": ["/etc"],
            })

    def test_action_ai_attribution_cannot_be_forged_by_browser(self):
        good = normalize_snmp_browser_payload("/api/snmp/actions", {
            "action": "repoll_device", "target": "router", "reason": "operator request",
        })
        self.assertIs(good["ai_involvement"], False)
        with self.assertRaises(ValueError):
            normalize_snmp_browser_payload("/api/snmp/actions", {
                "action": "repoll_device", "reason": "operator request", "ai_involvement": True,
            })

    def test_incident_window_is_bounded(self):
        self.assertEqual(
            normalize_snmp_browser_payload("/api/snmp/ai/incidents", {"minutes": 60})["minutes"],
            60,
        )
        with self.assertRaises(ValueError):
            normalize_snmp_browser_payload("/api/snmp/ai/incidents", {"minutes": 999999})


if __name__ == "__main__":
    unittest.main()
