#!/usr/bin/env python3
"""Regression coverage for the authenticated 2026-07-30 Edge1 inventory findings."""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER_ROOT = ROOT / "server"
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

RECONCILER_PATH = ROOT / "tools/security/reconcile-edge1-live-inventory.py"
MANIFEST_PATH = ROOT / "config/security/edge1-restricted-artifact-migration-manifest.json"
ACCESS_POLICY_PATH = ROOT / "config/security/edge1-authenticated-operations-policy.json"
INSTALLER_PATH = ROOT / "deploy/install-security-correlation-observability.sh"
VERIFIER_PATH = ROOT / "tools/security/verify-security-observability-live.sh"

SPEC = importlib.util.spec_from_file_location("reconcile_edge1_live_inventory", RECONCILER_PATH)
RECONCILER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(RECONCILER)

LIVE_ARTIFACTS = {
    "bitcoin-mining-history.json": {
        "sha256": "8cb03242c7ffef44256254d3f7131b66c75d206c2daf6dddf9756ef6607581fe",
        "bytes": 5260,
        "target_relative": "data/mining/bitcoin-mining-history.json",
        "repository_source": "tools/bitcoin_mining_history_summary.py",
    },
    "mining-operations.json": {
        "sha256": "a96c9e658ff3f1a7c946d3eb6aa69434977907c11359bd6cfac9858de126ca31",
        "bytes": 1555,
        "target_relative": "data/mining/mining-operations.json",
        "repository_source": "server/mining_operations_exporter.py",
    },
    "operations-changes.json": {
        "sha256": "50b547c98e03218658f48662958f812e30f9dae0d7bce5fde94f740e67667ce8",
        "bytes": 694,
        "target_relative": "data/operations/operations-changes.json",
        "repository_source": "server/operations_changes_exporter.py",
    },
    "operations-trends.json": {
        "sha256": "460d8fbc7b8b36e4c32ff58a9fb71ead6f77876f1682c692860ce086bf4d387a",
        "bytes": 354,
        "target_relative": "data/operations/operations-trends.json",
        "repository_source": "server/operations_trends_exporter.py",
    },
}


class Edge1LiveArtifactClassificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        cls.access_policy = json.loads(ACCESS_POLICY_PATH.read_text(encoding="utf-8"))

    def test_verified_live_artifacts_are_exact_manifest_entries(self) -> None:
        exact = {
            item["source_relative"]: item
            for item in self.manifest["known_exact_artifacts"]
        }
        for source, expected in LIVE_ARTIFACTS.items():
            with self.subTest(source=source):
                self.assertIn(source, exact)
                item = exact[source]
                self.assertEqual(item["target_relative"], expected["target_relative"])
                self.assertEqual(item["repository_source"], expected["repository_source"])
                self.assertTrue((ROOT / item["repository_source"]).is_file())
                self.assertEqual(item["required_scopes"], ["edge1.status.detail.read"])

    def test_live_records_map_without_unknowns_and_activation_stays_disabled(self) -> None:
        inventory = [
            {
                "path": f"/var/www/edge1-status/{source}",
                "sha256": expected["sha256"],
                "mode": "0644",
                "bytes": expected["bytes"],
            }
            for source, expected in LIVE_ARTIFACTS.items()
        ]
        result = RECONCILER.reconcile_inventory(
            self.manifest,
            self.access_policy,
            inventory,
        )
        self.assertEqual(result["counts"]["inventory"], 4)
        self.assertEqual(result["counts"]["mapped"], 4)
        self.assertEqual(result["unknown_preserved"], [])
        self.assertIs(result["source_mutation_allowed"], False)
        self.assertIs(result["deletion_authorized"], False)
        self.assertIs(result["staging_ready"], False)
        self.assertIs(result["cutover_ready"], False)

    def test_security_correlation_compatibility_symlink_is_exact_and_contained(self) -> None:
        installer = INSTALLER_PATH.read_text(encoding="utf-8")
        verifier = VERIFIER_PATH.read_text(encoding="utf-8")
        target = "security/correlation/data/security-correlation.json"
        self.assertIn(f'ln -sfn "{target}" "$LEGACY_LINK"', installer)
        self.assertIn(f'[ "$(readlink "$LEGACY_LINK")" = "{target}" ]', installer)
        self.assertIn(
            '[ "$(cat "$EVIDENCE_DIR/correlation-link-target.txt")" = '
            f'"{target}" ]',
            verifier,
        )
        resolved = pathlib.PurePosixPath("/var/www/edge1-status") / target
        self.assertEqual(
            str(resolved),
            "/var/www/edge1-status/security/correlation/data/security-correlation.json",
        )


if __name__ == "__main__":
    unittest.main()
