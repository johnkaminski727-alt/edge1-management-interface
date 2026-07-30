#!/usr/bin/env python3
"""Validation for the non-routed minimized Edge1 public status implementation."""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import os
import pathlib
import stat
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "server" / "edge1_public_status_exporter.py"
SCHEMA_PATH = ROOT / "schemas" / "wwcx-edge1-public-status-v1.schema.json"
POLICY_PATH = ROOT / "config" / "security" / "edge1-public-access-boundary-policy.json"
PAGE_PATH = ROOT / "src" / "web" / "public-status" / "index.html"
APP_PATH = ROOT / "src" / "web" / "public-status" / "app.js"
STYLE_PATH = ROOT / "src" / "web" / "public-status" / "style.css"
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "edge1_public_status"

SPEC = importlib.util.spec_from_file_location("edge1_public_status_exporter", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class Edge1PublicStatusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        cls.page = PAGE_PATH.read_text(encoding="utf-8")
        cls.app = APP_PATH.read_text(encoding="utf-8")
        cls.style = STYLE_PATH.read_text(encoding="utf-8")
        cls.source = MODULE_PATH.read_text(encoding="utf-8")
        cls.security = json.loads(
            (FIXTURE_ROOT / "security-operations-hostile.json").read_text(encoding="utf-8")
        )
        cls.network = json.loads(
            (FIXTURE_ROOT / "network-defense-hostile.json").read_text(encoding="utf-8")
        )
        cls.operations = json.loads(
            (FIXTURE_ROOT / "operations-health-hostile.json").read_text(encoding="utf-8")
        )
        cls.now = dt.datetime(2026, 7, 30, 19, 0, tzinfo=dt.timezone.utc)

    def build(self, notice: str = ""):
        return MODULE.build_public_status(
            self.security,
            self.network,
            self.operations,
            now=self.now,
            maintenance_notice=notice,
        )

    def test_schema_and_policy_contracts_match_the_output_shape(self) -> None:
        result = self.build()
        self.assertEqual(result["schema_version"], "wwcx.edge1-public-status.v1")
        self.assertEqual(
            self.schema["properties"]["schema_version"]["const"],
            result["schema_version"],
        )
        self.assertEqual(set(result), MODULE.PUBLIC_TOP_LEVEL_FIELDS)
        policy_fields = set(self.policy["public_contract"]["allowed_fields"])
        self.assertTrue(set(result).issubset(policy_fields))
        self.assertEqual(
            set(result["component_category"][0]),
            MODULE.PUBLIC_COMPONENT_FIELDS,
        )
        self.assertIs(result["read_only"], True)
        self.assertIs(result["traffic_controls_changed"], False)

    def test_hostile_source_detail_never_propagates(self) -> None:
        result = self.build(" Planned maintenance   only ")
        encoded = json.dumps(result, sort_keys=True)
        for forbidden_value in (
            "edge1-secret-host",
            "secret-kernel",
            "suricata.service",
            "10.10.10.10",
            "10.20.20.20",
            "192.0.2.10",
            "198.51.100.20",
            "45678",
            "evt-secret",
            "HOSTILE INTERNAL SIGNATURE",
            "wg0",
            "10.0.0.0/8",
            "deadbee",
            "INC-SECRET",
            "operations-report-secret.pdf",
            "must never propagate",
            "internal recommendation",
        ):
            self.assertNotIn(forbidden_value, encoded)
        forbidden_fields = set(self.policy["public_contract"]["forbidden_fields"])

        def walk(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    self.assertNotIn(key, forbidden_fields)
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        walk(result)
        self.assertEqual(result["maintenance_notice"], "Planned maintenance only")

    def test_component_counts_states_and_freshness_are_bounded(self) -> None:
        result = self.build()
        components = result["component_category"]
        self.assertEqual(
            [item["component_category"] for item in components],
            ["security", "network_defense", "operations"],
        )
        self.assertEqual(components[0]["component_state"], "healthy")
        self.assertEqual(components[0]["bounded_count"], 2)
        self.assertEqual(components[0]["freshness_bucket"], "fresh")
        self.assertEqual(components[1]["component_state"], "limited")
        self.assertEqual(components[1]["bounded_count"], 8)
        self.assertEqual(components[1]["freshness_bucket"], "fresh")
        self.assertEqual(components[2]["component_state"], "healthy")
        self.assertEqual(components[2]["bounded_count"], 3)
        self.assertEqual(components[2]["freshness_bucket"], "aging")
        self.assertEqual(result["overall_state"], "limited")

    def test_stale_or_missing_inputs_degrade_without_source_errors(self) -> None:
        old = dict(self.security)
        old["generated_at"] = "2026-07-30T18:00:00+00:00"
        result = MODULE.build_public_status(
            old,
            None,
            None,
            now=self.now,
        )
        components = result["component_category"]
        self.assertEqual(components[0]["component_state"], "attention")
        self.assertEqual(components[0]["freshness_bucket"], "stale")
        self.assertEqual(components[1]["component_state"], "unavailable")
        self.assertEqual(components[1]["freshness_bucket"], "unknown")
        self.assertEqual(components[2]["component_state"], "unavailable")
        self.assertEqual(result["overall_state"], "attention")
        encoded = json.dumps(result)
        self.assertNotIn("missing", encoded.lower())
        self.assertNotIn("error", encoded.lower())
        self.assertNotIn(str(FIXTURE_ROOT), encoded)

    def test_count_and_notice_limits_are_enforced(self) -> None:
        security = dict(self.security)
        security["recent_alerts"] = [{}] * 2000
        network = dict(self.network)
        network["summary"] = {"available_source_count": 5000}
        operations = dict(self.operations)
        operations["checks"] = [{}] * 5000
        result = MODULE.build_public_status(
            security,
            network,
            operations,
            now=self.now,
            maintenance_notice=" x " * 500,
        )
        components = result["component_category"]
        self.assertEqual(components[0]["bounded_count"], 999)
        self.assertEqual(components[1]["bounded_count"], 99)
        self.assertEqual(components[2]["bounded_count"], 99)
        self.assertLessEqual(len(result["maintenance_notice"]), 160)

    def test_atomic_output_is_build_scoped_and_non_executable(self) -> None:
        self.assertTrue(
            str(MODULE.DEFAULT_OUTPUT).endswith(
                "build/edge1-public-status/public/status.json"
            )
        )
        self.assertNotIn("/var/www", str(MODULE.DEFAULT_OUTPUT))
        with tempfile.TemporaryDirectory() as tmp:
            output = pathlib.Path(tmp) / "public" / "status.json"
            MODULE.write_public_status(self.build(), output)
            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8"))["schema_version"],
                "wwcx.edge1-public-status.v1",
            )
            self.assertFalse(output.with_suffix(".json.tmp").exists())
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o644)

    def test_exporter_has_no_command_network_or_live_publication_path(self) -> None:
        for token in (
            "subprocess",
            "socket",
            "requests",
            "urllib.request",
            "os.system",
            "Popen(",
            "/var/www",
            "/etc/apache",
            "systemctl",
            "apachectl",
        ):
            self.assertNotIn(token, self.source)
        self.assertIn('parser.add_argument("--security", type=Path, required=True)', self.source)
        self.assertIn('parser.add_argument("--network-defense", type=Path, required=True)', self.source)
        self.assertIn('parser.add_argument("--operations-health", type=Path, required=True)', self.source)

    def test_page_consumes_only_the_minimized_document(self) -> None:
        self.assertIn('<script src="./app.js" defer></script>', self.page)
        self.assertIn('<link rel="stylesheet" href="./style.css">', self.page)
        self.assertNotIn("<style", self.page.lower())
        policy_csp = self.policy["public_contract"]["content_security_policy"]
        self.assertIn(f'content="{policy_csp}"', self.page)
        self.assertNotIn("unsafe-inline", self.page)
        self.assertIn('const STATUS_URL = "./public/status.json";', self.app)
        self.assertIn('cache: "no-store"', self.app)
        self.assertIn('credentials: "omit"', self.app)
        self.assertTrue(self.style.strip())
        policy_outputs = {
            item["path"]: item["content"]
            for item in self.policy["future_public_outputs"]
        }
        self.assertEqual(
            policy_outputs["/edge1-status/public/status.json"],
            "aggregate_status_contract_only",
        )
        for forbidden_feed in (
            "security-operations.json",
            "security-correlation.json",
            "network-defense.json",
            "operations-inventory.json",
            "operations-network.json",
            "operations-version.json",
            "operations-incidents.json",
            "bitcoin-wallet.json",
            "bitcoin-mining.json",
            "reports/index.json",
        ):
            self.assertNotIn(forbidden_feed, self.page)
            self.assertNotIn(forbidden_feed, self.app)
            self.assertNotIn(forbidden_feed, self.style)
        self.assertNotIn("/edge1-ops/", self.page)
        self.assertNotIn("/edge1-status/security/", self.page)

    def test_implementation_adds_no_deployment_or_runtime_activation_assets(self) -> None:
        implementation_paths = (
            ROOT / "server" / "edge1_public_status_exporter.py",
            ROOT / "schemas" / "wwcx-edge1-public-status-v1.schema.json",
            ROOT / "src" / "web" / "public-status" / "index.html",
            ROOT / "src" / "web" / "public-status" / "app.js",
            ROOT / "src" / "web" / "public-status" / "style.css",
        )
        for path in implementation_paths:
            self.assertTrue(path.exists(), path)
        for forbidden_path in (
            ROOT / "deploy" / "install-edge1-public-status.sh",
            ROOT / "deploy" / "systemd" / "wwcx-edge1-public-status.service",
            ROOT / "deploy" / "systemd" / "wwcx-edge1-public-status.timer",
        ):
            self.assertFalse(forbidden_path.exists(), forbidden_path)


if __name__ == "__main__":
    unittest.main()
