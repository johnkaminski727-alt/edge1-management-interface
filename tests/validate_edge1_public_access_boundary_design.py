#!/usr/bin/env python3
"""Static validation for the disabled Edge1 public access boundary design."""

from __future__ import annotations

import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "security" / "edge1-public-access-boundary-policy.json"
SCHEMA_PATH = ROOT / "schemas" / "wwcx-edge1-public-access-boundary-policy-v1.schema.json"
DESIGN_PATH = ROOT / "docs" / "security" / "edge1-public-access-boundary-design-20260730.md"
REGISTER_PATH = ROOT / "registers" / "edge1-public-access-boundary-design-register-20260730.md"
DOMAIN_REGISTER = ROOT / "registers" / "edge1-status-domain-acceptance-20260729.md"
OPERATIONS_PAGE = ROOT / "src" / "web" / "operations-center" / "index.html"
PUBLISHER = ROOT / "deploy" / "operations-center" / "publish.sh"
INVENTORY = ROOT / "server" / "operations_inventory_exporter.py"
NETWORK = ROOT / "server" / "operations_network_exporter.py"
VERSION = ROOT / "server" / "operations_version_exporter.py"
CHANGES = ROOT / "server" / "operations_changes_exporter.py"
AUTOMATION = ROOT / "server" / "operations_automation_health_exporter.py"
INCIDENTS = ROOT / "server" / "operations_incident_exporter.py"
INCIDENT_HISTORY = ROOT / "server" / "operations_incident_history_exporter.py"
REPORT = ROOT / "server" / "operations_report_exporter.py"


class Edge1PublicAccessBoundaryDesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.design = DESIGN_PATH.read_text(encoding="utf-8")
        cls.register = REGISTER_PATH.read_text(encoding="utf-8")
        cls.domain_register = DOMAIN_REGISTER.read_text(encoding="utf-8")
        cls.operations_page = OPERATIONS_PAGE.read_text(encoding="utf-8")
        cls.publisher = PUBLISHER.read_text(encoding="utf-8")
        cls.inventory = INVENTORY.read_text(encoding="utf-8")
        cls.network = NETWORK.read_text(encoding="utf-8")
        cls.version = VERSION.read_text(encoding="utf-8")
        cls.changes = CHANGES.read_text(encoding="utf-8")
        cls.automation = AUTOMATION.read_text(encoding="utf-8")
        cls.incidents = INCIDENTS.read_text(encoding="utf-8")
        cls.incident_history = INCIDENT_HISTORY.read_text(encoding="utf-8")
        cls.report = REPORT.read_text(encoding="utf-8")

    def test_policy_is_disabled_and_non_authorizing(self) -> None:
        self.assertEqual(
            self.policy["contract"],
            "wwcx.edge1-public-access-boundary-policy.v1",
        )
        self.assertEqual(self.policy["status"], "design_only")
        self.assertIs(self.policy["enabled"], False)
        self.assertIs(self.policy["deployment_authorized"], False)
        self.assertEqual(self.policy["domain"], "edge1.ww.cx")
        self.assertEqual(
            self.schema["properties"]["contract"]["const"],
            self.policy["contract"],
        )
        target = self.policy["target_boundary"]
        for key in (
            "public_change_authorized",
            "authentication_change_authorized",
            "certificate_change_authorized",
            "proxy_change_authorized",
            "listener_change_authorized",
        ):
            self.assertIs(target[key], False, key)

    def test_current_domain_and_publication_evidence_is_present(self) -> None:
        self.assertIn("Domain: `edge1.ww.cx`", self.domain_register)
        self.assertIn("https://edge1.ww.cx/edge1-status/", self.domain_register)
        self.assertIn("security-operations.json", self.domain_register)
        self.assertIn("security-correlation.json", self.domain_register)
        self.assertIn("network-defense/data/network-defense.json", self.domain_register)
        self.assertIn('DEST="/var/www/edge1-status/index.html"', self.publisher)
        self.assertIn('install -m 0644 "$SOURCE" "$DEST"', self.publisher)

    def test_operations_page_consumes_mixed_detailed_feeds(self) -> None:
        for feed in (
            "security-operations.json",
            "bitcoin-wallet.json",
            "bitcoin-mining.json",
            "operations-health.json",
            "operations-automation.json",
            "operations-version.json",
            "operations-inventory.json",
            "operations-network.json",
            "operations-telephony.json",
            "operations-messaging.json",
            "operations-carrier.json",
            "operations-incidents.json",
            "operations-incident-history.json",
            "reports/index.json",
        ):
            self.assertIn(feed, self.operations_page)
        self.assertIn('cache:"no-store"', self.operations_page)

    def test_repository_evidence_contains_restricted_detail(self) -> None:
        for marker in (
            '"host": platform.node()',
            '"kernel": platform.release()',
            '"running_services"',
        ):
            self.assertIn(marker, self.inventory)
        for marker in (
            '"interfaces"',
            '"routes"',
            '"wireguard"',
            '"resolver"',
        ):
            self.assertIn(marker, self.network)
        for marker in ('"branch"', '"commit"', '"dirty"'):
            self.assertIn(marker, self.version)
        for marker in ('"recent_commits"', '"message"', '"clean"'):
            self.assertIn(marker, self.changes)
        self.assertIn('"name": name', self.automation)
        self.assertIn('"next_run": next_run', self.automation)
        self.assertIn('"active_incidents"', self.incidents)
        self.assertIn('"incidents"', self.incident_history)
        self.assertIn('REPORT_DIR = ROOT / "reports"', self.report)
        self.assertIn('"changes": changes', self.report)
        self.assertIn('"correlation": correlation', self.report)

    def test_route_matrix_separates_public_summary_from_restricted_detail(self) -> None:
        routes = self.policy["route_classes"]
        self.assertGreaterEqual(len(routes), 20)
        paths = [item["path"] for item in routes]
        self.assertEqual(len(paths), len(set(paths)))
        by_path = {item["path"]: item for item in routes}
        self.assertEqual(
            by_path["/edge1-status/"]["target_class"],
            "public_minimized_summary",
        )
        for path in (
            "/edge1-status/security/",
            "/edge1-status/security/correlation.html",
            "/edge1-status/security-operations.json",
            "/edge1-status/operations-inventory.json",
            "/edge1-status/operations-network.json",
            "/edge1-status/operations-version.json",
            "/edge1-status/operations-changes.json",
            "/edge1-status/operations-incidents.json",
            "/edge1-status/operations-incident-history.json",
            "/edge1-status/reports/",
        ):
            self.assertTrue(by_path[path]["target_class"].startswith("restricted_"))
        public_paths = {item["path"] for item in self.policy["future_public_outputs"]}
        self.assertEqual(
            public_paths,
            {"/edge1-status/", "/edge1-status/public/status.json"},
        )

    def test_public_contract_is_allowlist_only_and_forbids_sensitive_fields(self) -> None:
        contract = self.policy["public_contract"]
        allowed = set(contract["allowed_fields"])
        forbidden = set(contract["forbidden_fields"])
        self.assertFalse(allowed & forbidden)
        for field in (
            "host",
            "kernel",
            "running_services",
            "branch",
            "commit",
            "interface",
            "route",
            "wireguard",
            "source_address",
            "destination_address",
            "flow_id",
            "incident_history",
            "report_filename",
            "raw_error",
        ):
            self.assertIn(field, forbidden)
        self.assertEqual(contract["cache_control"], "no-store, max-age=0")
        self.assertEqual(contract["referrer_policy"], "no-referrer")
        self.assertEqual(contract["x_content_type_options"], "nosniff")
        self.assertEqual(contract["cors_allow_origin"], "none")
        self.assertIs(contract["directory_listing"], False)

    def test_future_restricted_access_fails_closed_and_is_separately_scoped(self) -> None:
        restricted = self.policy["future_restricted_access"]
        self.assertEqual(restricted["api_scope"], "edge1.status.detail.read")
        self.assertEqual(
            restricted["security_history_scope"],
            "security.suricata.history.read",
        )
        self.assertIs(restricted["browser_authentication_design_required"], True)
        self.assertIs(restricted["anonymous_fallback"], False)
        self.assertIs(restricted["audit_log_required"], True)
        self.assertIs(restricted["rate_limit_required"], True)
        self.assertEqual(restricted["authorization_failure_statuses"], [401, 403])
        self.assertEqual(restricted["unpublished_status"], 404)

    def test_rollout_requires_authorization_and_rollback_preserves_data(self) -> None:
        rollout = self.policy["rollout"]
        self.assertIs(rollout["phase_0_read_only_inventory"], True)
        self.assertIs(rollout["phase_1_build_minimized_outputs_without_routing"], True)
        self.assertIs(
            rollout["phase_3_public_cutover_requires_explicit_authorization"],
            True,
        )
        self.assertIs(
            rollout["phase_4_remove_sensitive_public_artifacts_requires_explicit_authorization"],
            True,
        )
        rollback = self.policy["rollback"]
        self.assertIs(rollback["preserve_operational_data"], True)
        self.assertIs(rollback["data_deletion_not_part_of_rollback"], True)
        self.assertIs(rollback["dns_change_required"], False)
        self.assertIs(rollback["certificate_change_required"], False)
        self.assertIs(rollback["firewall_change_required"], False)

    def test_design_explicitly_makes_no_live_boundary_change(self) -> None:
        for marker in (
            "should not remain unchanged as the long-term access boundary",
            "This document defines that target but makes no Apache",
            "A successful HTTP status alone is insufficient",
            "This design does not authorize",
        ):
            self.assertIn(marker, self.design)
        for marker in (
            "No live access, proxy, authentication, certificate, DNS, listener, or published-file change",
            "Repository evidence does not prove the complete live Apache authorization",
            "This design does not authorize proxy, Apache, authentication",
        ):
            self.assertIn(marker, self.register)
        acceptance = self.policy["acceptance"]
        self.assertIs(acceptance["traffic_controls_changed"], False)
        self.assertIs(acceptance["live_change_authorized"], False)


if __name__ == "__main__":
    unittest.main()
