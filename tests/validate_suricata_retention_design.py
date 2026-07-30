#!/usr/bin/env python3
"""Static validation for the disabled protected Suricata retention design."""

from __future__ import annotations

import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "security" / "suricata-protected-retention-policy.json"
SCHEMA_PATH = ROOT / "schemas" / "wwcx-suricata-protected-retention-policy-v1.schema.json"
DESIGN_PATH = ROOT / "docs" / "security" / "suricata-protected-retention-design-20260730.md"
REGISTER_PATH = ROOT / "registers" / "suricata-protected-retention-design-register-20260730.md"
COLLECTOR_PATH = ROOT / "server" / "bigbird_ops_collect.py"
EXPORTER_PATH = ROOT / "server" / "security_operations_exporter.py"


class SuricataRetentionDesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.design = DESIGN_PATH.read_text(encoding="utf-8")
        cls.register = REGISTER_PATH.read_text(encoding="utf-8")
        cls.collector = COLLECTOR_PATH.read_text(encoding="utf-8")
        cls.exporter = EXPORTER_PATH.read_text(encoding="utf-8")

    def test_policy_is_disabled_and_requires_explicit_activation(self) -> None:
        self.assertEqual(
            self.policy["contract"],
            "wwcx.suricata-protected-retention-policy.v1",
        )
        self.assertEqual(self.policy["status"], "design_only")
        self.assertIs(self.policy["enabled"], False)
        self.assertIs(self.policy["activation_requires_explicit_authorization"], True)
        self.assertIs(self.policy["acceptance"]["deployment_authorized"], False)
        self.assertEqual(
            self.schema["properties"]["contract"]["const"],
            self.policy["contract"],
        )
        self.assertEqual(
            self.schema["properties"]["status"]["const"],
            "design_only",
        )

    def test_ingestion_uses_only_the_sanitized_collector_contract(self) -> None:
        ingest = self.policy["ingest"]
        self.assertEqual(
            ingest["source"],
            "/var/lib/bigbird/operations-center/latest.json",
        )
        self.assertNotIn("/var/log/suricata", ingest["source"])
        self.assertIs(ingest["raw_eve_allowed"], False)
        self.assertEqual(
            ingest["required_source_schema"],
            "wwcx.suricata-source-alert.v1",
        )
        self.assertEqual(ingest["interval_seconds"], 120)
        self.assertEqual(ingest["max_alerts_per_run"], 100)
        self.assertIn("SURICATA_ALERT_SCHEMA = 'wwcx.suricata-source-alert.v1'", self.collector)
        self.assertIn("'recent_alerts': recent[-100:]", self.collector)
        self.assertIn("MAX_ALERTS = 50", self.exporter)

    def test_deduplication_contract_is_deterministic_and_bounded(self) -> None:
        dedupe = self.policy["ingest"]["deduplication"]
        self.assertEqual(dedupe["algorithm"], "sha256")
        self.assertEqual(dedupe["unique_constraint"], "event_key")
        fields = dedupe["canonical_fields"]
        self.assertEqual(len(fields), len(set(fields)))
        for required in (
            "timestamp",
            "signature",
            "signature_id",
            "flow_id",
            "event_id",
            "source",
            "destination",
        ):
            self.assertIn(required, fields)

    def test_time_size_event_and_page_limits_are_consistent(self) -> None:
        storage = self.policy["storage"]
        self.assertEqual(storage["retention_days"], 30)
        self.assertEqual(storage["max_database_bytes"], 256 * 1024 * 1024)
        self.assertEqual(storage["max_events"], 100000)
        self.assertEqual(storage["page_size_bytes"], 4096)
        self.assertEqual(storage["max_page_count"], 65536)
        self.assertEqual(
            storage["page_size_bytes"] * storage["max_page_count"],
            storage["max_database_bytes"],
        )
        self.assertEqual(storage["prune_target_percent"], 90)
        self.assertIs(storage["automatic_offhost_backup"], False)
        self.assertIs(storage["legal_hold_export_required"], True)

    def test_storage_and_query_are_root_only_and_non_public(self) -> None:
        storage = self.policy["storage"]
        query = self.policy["query"]
        self.assertTrue(storage["database"].startswith("/var/lib/bigbird-security/"))
        self.assertTrue(storage["status_file"].startswith("/var/lib/bigbird-security/"))
        self.assertNotIn("/var/www", storage["database"])
        self.assertNotIn("/var/www", storage["status_file"])
        self.assertEqual(storage["owner"], "root")
        self.assertEqual(storage["group"], "root")
        self.assertEqual(storage["directory_mode"], "0700")
        self.assertEqual(storage["database_mode"], "0600")
        self.assertEqual(storage["status_mode"], "0600")
        self.assertIs(query["network_listener"], False)
        self.assertIs(query["public_endpoint"], False)
        self.assertIs(query["local_cli_only"], True)
        self.assertEqual(query["default_window_hours"], 24)
        self.assertEqual(query["max_window_days"], 7)
        self.assertEqual(query["default_limit"], 100)
        self.assertEqual(query["max_limit"], 500)
        self.assertEqual(
            query["future_operations_api_scope"],
            "security.suricata.history.read",
        )
        self.assertIs(query["authentication_boundary_change_authorized"], False)

    def test_privacy_contract_excludes_sensitive_and_unbounded_content(self) -> None:
        privacy = self.policy["privacy"]
        self.assertIs(privacy["sanitized_alerts_only"], True)
        for key in (
            "packet_payloads_included",
            "raw_events_included",
            "raw_logs_included",
            "credentials_included",
            "private_keys_included",
            "arbitrary_metadata_included",
        ):
            self.assertIs(privacy[key], False, key)
        self.assertLessEqual(len(privacy["approved_fields"]), 20)
        self.assertEqual(
            len(privacy["approved_fields"]),
            len(set(privacy["approved_fields"])),
        )
        for marker in (
            "Retaining raw `eve.json`: rejected",
            "no HTTP route",
            "no public `edge1.ww.cx` history page",
            "Endpoint addresses are operationally sensitive",
        ):
            self.assertIn(marker, self.design)

    def test_incident_promotion_requires_authorization_and_hashing(self) -> None:
        promotion = self.policy["incident_promotion"]
        self.assertIs(promotion["automatic"], False)
        self.assertTrue(
            promotion["evidence_root"].startswith(
                "/var/lib/wwcx-deployment-evidence/suricata-history-holds"
            )
        )
        self.assertIs(promotion["sha256_manifest_required"], True)
        self.assertIs(promotion["authorization_record_required"], True)
        self.assertEqual(
            promotion["retention_class"],
            "security_and_access_records",
        )
        self.assertIn("30-day rolling history is not the authoritative incident archive", self.register)

    def test_rollback_preserves_data_and_control_planes(self) -> None:
        rollback = self.policy["rollback"]
        acceptance = self.policy["acceptance"]
        self.assertIs(rollback["preserve_database_by_default"], True)
        self.assertIs(
            rollback["data_destruction_requires_separate_authorization"],
            True,
        )
        for key in (
            "suricata_configuration_changed",
            "suricata_service_changed",
            "traffic_controls_changed",
            "authentication_boundary_changed",
            "public_access_changed",
        ):
            self.assertIs(acceptance[key], False, key)
        for marker in (
            "No Suricata service restart",
            "preserve the database by default",
            "This phase does not include runtime code",
        ):
            self.assertIn(marker, self.design)


if __name__ == "__main__":
    unittest.main()
