#!/usr/bin/env python3
"""Tests for the read-only Edge1 restricted-artifact migration manifest."""

from __future__ import annotations

import copy
import importlib.util
import json
import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER_ROOT = ROOT / "server"
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))
MODULE_PATH = SERVER_ROOT / "edge1_restricted_artifact_manifest.py"
MANIFEST_PATH = ROOT / "config" / "security" / "edge1-restricted-artifact-migration-manifest.json"
ACCESS_POLICY_PATH = ROOT / "config" / "security" / "edge1-authenticated-operations-policy.json"
OPERATIONS_PAGE = ROOT / "src" / "web" / "operations-center" / "index.html"
SECURITY_PAGE = ROOT / "src" / "web" / "security" / "index.html"

SPEC = importlib.util.spec_from_file_location("edge1_restricted_artifact_manifest", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class Edge1RestrictedArtifactManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        cls.access_policy = json.loads(ACCESS_POLICY_PATH.read_text(encoding="utf-8"))
        cls.source = MODULE_PATH.read_text(encoding="utf-8")
        cls.operations_page = OPERATIONS_PAGE.read_text(encoding="utf-8")
        cls.security_page = SECURITY_PAGE.read_text(encoding="utf-8")

    @staticmethod
    def inventory(path: str, marker: str = "a"):
        return {
            "path": f"/var/www/edge1-status/{path}",
            "sha256": marker * 64,
            "mode": "0644",
            "bytes": 123,
        }

    def test_committed_manifest_is_disabled_and_non_destructive(self) -> None:
        MODULE.validate_manifest(self.manifest, self.access_policy)
        self.assertEqual(self.manifest["contract"], MODULE.CONTRACT)
        self.assertEqual(self.manifest["status"], "design_only")
        for key in (
            "enabled",
            "staging_authorized",
            "cutover_authorized",
            "deletion_authorized",
            "source_mutation_allowed",
        ):
            self.assertIs(self.manifest[key], False)
        self.assertEqual(self.manifest["unknown_artifact_action"], "preserve_review")
        self.assertEqual(self.manifest["duplicate_target_action"], "block")
        self.assertEqual(self.manifest["missing_known_action"], "report")
        self.assertIs(self.manifest["acceptance"]["public_cutover_performed"], False)
        self.assertIs(self.manifest["acceptance"]["detailed_artifacts_removed"], False)
        self.assertIs(self.manifest["acceptance"]["live_change_authorized"], False)

    def test_exact_and_prefix_mappings_are_unique_safe_and_registered(self) -> None:
        exact_sources = set()
        exact_targets = set()
        for item in self.manifest["known_exact_artifacts"]:
            source = MODULE.safe_relative(item["source_relative"])
            target = MODULE.safe_relative(item["target_relative"])
            self.assertNotIn(source, exact_sources)
            self.assertNotIn(target, exact_targets)
            exact_sources.add(source)
            exact_targets.add(target)
            route = MODULE.route_contract(
                self.access_policy,
                target,
                item["required_scopes"],
            )
            self.assertEqual(route["required_scopes"], item["required_scopes"])
            if item["repository_source"] is not None:
                self.assertTrue((ROOT / item["repository_source"]).is_file(), item["repository_source"])

        prefix_sources = set()
        prefix_targets = set()
        for group in self.manifest["known_prefix_groups"]:
            source = MODULE.safe_relative(group["source_prefix"], directory=True)
            target = MODULE.safe_relative(group["target_prefix"], directory=True)
            self.assertNotIn(source, prefix_sources)
            self.assertNotIn(target, prefix_targets)
            prefix_sources.add(source)
            prefix_targets.add(target)
            route = MODULE.route_contract(
                self.access_policy,
                target + "inventory-probe",
                group["required_scopes"],
            )
            self.assertEqual(route["required_scopes"], group["required_scopes"])

    def test_operations_center_literal_public_references_are_covered(self) -> None:
        references = set(re.findall(r'["\'](/edge1-status/[^"\']*)', self.operations_page))
        references.add("/edge1-status/security-operations.json")
        exact = {item["source_relative"] for item in self.manifest["known_exact_artifacts"]}
        prefixes = {item["source_prefix"] for item in self.manifest["known_prefix_groups"]}

        uncovered = []
        for reference in references:
            if reference == "/edge1-status/":
                relative = "index.html"
            else:
                relative = reference[len("/edge1-status/"):]
            covered = relative in exact or any(
                relative == prefix or relative.startswith(prefix)
                for prefix in prefixes
            )
            if not covered:
                uncovered.append(reference)
        self.assertFalse(uncovered, uncovered)
        self.assertIn('const ENDPOINT="/edge1-status/security-operations.json"', self.security_page)

    def test_manifest_rejects_drift_and_unsafe_paths(self) -> None:
        mutations = (
            lambda value: value.update(source_mutation_allowed=True),
            lambda value: value.update(unknown_artifact_action="delete"),
            lambda value: value.update(deletion_authorized=True),
            lambda value: value["known_exact_artifacts"][0].update(source_relative="../index.html"),
            lambda value: value["known_exact_artifacts"][1].update(
                target_relative=value["known_exact_artifacts"][0]["target_relative"]
            ),
            lambda value: value["known_prefix_groups"][0].update(live_enumeration_required=False),
            lambda value: value["known_exact_artifacts"][0].update(required_scopes=[]),
        )
        for mutate in mutations:
            value = copy.deepcopy(self.manifest)
            mutate(value)
            with self.subTest(mutate=mutate):
                with self.assertRaises(ValueError):
                    MODULE.validate_manifest(value, self.access_policy)

    def test_partial_inventory_maps_known_and_preserves_unknown(self) -> None:
        result = MODULE.reconcile_inventory(
            self.manifest,
            self.access_policy,
            [
                self.inventory("index.html", "a"),
                self.inventory("operations-health.json", "b"),
                self.inventory("bitcoin/index.html", "c"),
                self.inventory("unclassified-secret.txt", "d"),
            ],
        )
        self.assertEqual(result["counts"]["inventory"], 4)
        self.assertEqual(result["counts"]["mapped"], 3)
        self.assertEqual(result["counts"]["unknown_preserved"], 1)
        self.assertGreater(result["counts"]["missing_known"], 0)
        self.assertEqual(result["unknown_preserved"][0]["action"], "preserve_review")
        self.assertEqual(result["unknown_preserved"][0]["source_relative"], "unclassified-secret.txt")
        self.assertIs(result["source_mutation_allowed"], False)
        self.assertIs(result["deletion_authorized"], False)
        self.assertIs(result["staging_ready"], False)
        self.assertIs(result["cutover_ready"], False)

        mapped = {item["source_relative"]: item for item in result["mapped"]}
        self.assertEqual(mapped["index.html"]["target_route"], "/edge1-ops/")
        self.assertEqual(
            mapped["operations-health.json"]["target_route"],
            "/edge1-ops/data/operations/operations-health.json",
        )
        self.assertEqual(mapped["bitcoin/index.html"]["provenance"], "prefix_live_enumeration")

    def test_complete_exact_inventory_has_no_missing_known_but_stays_disabled(self) -> None:
        inventory = [
            self.inventory(item["source_relative"], format(index % 16, "x"))
            for index, item in enumerate(self.manifest["known_exact_artifacts"], start=1)
        ]
        result = MODULE.reconcile_inventory(self.manifest, self.access_policy, inventory)
        self.assertEqual(result["missing_known"], [])
        self.assertEqual(result["unknown_preserved"], [])
        self.assertEqual(result["counts"]["mapped"], len(inventory))
        self.assertIs(result["staging_ready"], False)
        self.assertIs(result["cutover_ready"], False)

    def test_inventory_validation_rejects_duplicates_and_invalid_metadata(self) -> None:
        duplicate = self.inventory("index.html")
        with self.assertRaises(ValueError):
            MODULE.reconcile_inventory(
                self.manifest,
                self.access_policy,
                [duplicate, dict(duplicate)],
            )
        invalid_cases = (
            {"path": "/etc/passwd", "sha256": "a" * 64, "mode": "0644", "bytes": 1},
            {"path": "/var/www/edge1-status/../secret", "sha256": "a" * 64, "mode": "0644", "bytes": 1},
            {"path": "/var/www/edge1-status/index.html", "sha256": "short", "mode": "0644", "bytes": 1},
            {"path": "/var/www/edge1-status/index.html", "sha256": "a" * 64, "mode": "0999", "bytes": 1},
            {"path": "/var/www/edge1-status/index.html", "sha256": "a" * 64, "mode": "0644", "bytes": -1},
        )
        for item in invalid_cases:
            with self.subTest(item=item):
                with self.assertRaises(ValueError):
                    MODULE.normalize_inventory_item(item)

    def test_module_contains_no_mutation_or_deployment_operation(self) -> None:
        for token in (
            "shutil",
            "subprocess",
            "os.remove",
            ".unlink(",
            ".rename(",
            ".replace(",
            "chmod(",
            "chown(",
            "systemctl",
            "apachectl",
            "a2enconf",
            "a2dissite",
            "serve_forever",
            "http.server",
            "socket",
        ):
            self.assertNotIn(token, self.source)
        self.assertIn("This module is read-only", self.source)
        self.assertIn("preserve_review", self.source)
        self.assertIn("duplicate target mapping blocked", self.source)
        self.assertFalse((ROOT / "deploy" / "apply-edge1-restricted-artifact-migration.sh").exists())


if __name__ == "__main__":
    unittest.main()
