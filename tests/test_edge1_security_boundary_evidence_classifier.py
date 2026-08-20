#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/security/classify-edge1-security-boundary-evidence.py"
SPEC = importlib.util.spec_from_file_location("edge1_security_boundary_classifier", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

RULES = MODULE.REVIEWED_RESIDUAL_RULES


class SecurityBoundaryEvidenceClassifierTests(unittest.TestCase):
    def build_fixture(self, root: pathlib.Path):
        repo = root / "repo"
        status = root / "status"
        evidence_root = root / "evidence"
        evidence = evidence_root / "20260820T010000Z"
        status.mkdir(parents=True)
        evidence.mkdir(parents=True)

        static_source = repo / RULES["network-sensor/index.html"]["repository_source"]
        static_source.parent.mkdir(parents=True)
        static_source.write_text("<html>reviewed static page</html>\n", encoding="utf-8")

        for relative, rule in RULES.items():
            live = status / relative
            live.parent.mkdir(parents=True, exist_ok=True)
            kind = rule["classification"]
            if kind == "repository_static":
                live.write_bytes(static_source.read_bytes())
            elif kind == "generated_json":
                live.write_text(json.dumps({"generated": True, "path": relative}), encoding="utf-8")
            else:
                live.write_text("preserved historical html\n", encoding="utf-8")

        target = status / MODULE.COMPATIBILITY_TARGET_RELATIVE
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('{"read_only": true}\n', encoding="utf-8")
        link = status / MODULE.COMPATIBILITY_LINK_RELATIVE
        link.symlink_to(MODULE.COMPATIBILITY_TARGET_RELATIVE)

        unknowns = [
            {
                "source_relative": relative,
                "sha256": "historical-snapshot-intentionally-not-used",
                "mode": "0644",
                "bytes": 1,
                "action": "preserve_review",
                "reason": "not_in_repository_declared_manifest",
            }
            for relative in RULES
        ]
        (evidence / "result.json").write_text(
            json.dumps(
                {
                    "contract": "wwcx.edge1-security-boundary-live-inventory-result.v1",
                    "read_only_host_inventory": True,
                    "live_configuration_changed": False,
                    "source_tree_mutated": False,
                    "credentials_collected": False,
                    "cookie_values_recorded": False,
                    "traffic_controls_changed": False,
                    "inventory_records": 164,
                    "mapped_records": 160,
                    "unknown_preserved": 4,
                    "missing_known": 0,
                    "filesystem_anomalies": 1,
                    "apache_config_test_passed": True,
                    "staging_ready": False,
                    "cutover_ready": False,
                }
            ),
            encoding="utf-8",
        )
        (evidence / "reconciliation.json").write_text(
            json.dumps({"unknown_preserved": unknowns}), encoding="utf-8"
        )
        (evidence / "public-filesystem-inventory.json").write_text("[]", encoding="utf-8")
        (evidence / "public-filesystem-anomalies.json").write_text(
            json.dumps([{"path": str(link), "type": "symlink"}]), encoding="utf-8"
        )
        return repo, status, evidence_root, evidence

    def test_classifies_exact_reviewed_set_and_compatibility_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo, status, evidence_root, evidence = self.build_fixture(pathlib.Path(temporary))
            value = MODULE.classify(repo_root=repo, status_root=status, evidence_root=evidence_root)
            self.assertEqual(value["contract"], "wwcx.edge1-security-boundary-residual-classification.v2")
            self.assertEqual(value["selected_evidence_dir"], str(evidence))
            self.assertEqual(value["classified_unknown_count"], 4)
            classes = {item["source_relative"]: item["classification"] for item in value["classified_unknown_records"]}
            self.assertEqual(classes, {name: rule["classification"] for name, rule in RULES.items()})
            self.assertTrue(value["classified_filesystem_anomaly"]["contained_within_status_root"])
            self.assertFalse(value["file_contents_printed"])
            self.assertFalse(value["live_files_mutated"])

    def test_dynamic_json_may_change_size_and_hash_but_must_remain_valid_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo, status, evidence_root, _ = self.build_fixture(pathlib.Path(temporary))
            dynamic = status / "network-sensor/data/network-sensor.json"
            dynamic.write_text(json.dumps({"new": "runtime value", "items": list(range(20))}), encoding="utf-8")
            value = MODULE.classify(repo_root=repo, status_root=status, evidence_root=evidence_root)
            item = next(x for x in value["classified_unknown_records"] if x["source_relative"] == "network-sensor/data/network-sensor.json")
            self.assertTrue(item["json_valid"])
            self.assertFalse(item["historical_size_hash_enforced"])
            dynamic.write_text("not-json", encoding="utf-8")
            with self.assertRaises(json.JSONDecodeError):
                MODULE.classify(repo_root=repo, status_root=status, evidence_root=evidence_root)

    def test_static_page_fails_closed_on_repository_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo, status, evidence_root, _ = self.build_fixture(pathlib.Path(temporary))
            (status / "network-sensor/index.html").write_text("changed\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "does not match repository source"):
                MODULE.classify(repo_root=repo, status_root=status, evidence_root=evidence_root)

    def test_preserved_unresolved_may_differ_from_historical_snapshot_without_overwrite_authority(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo, status, evidence_root, _ = self.build_fixture(pathlib.Path(temporary))
            unresolved = status / "operations-center/snmp.html"
            unresolved.write_text("preserved but provenance remains unresolved\n", encoding="utf-8")
            value = MODULE.classify(repo_root=repo, status_root=status, evidence_root=evidence_root)
            item = next(x for x in value["classified_unknown_records"] if x["source_relative"] == "operations-center/snmp.html")
            self.assertEqual(item["repository_provenance"], "unresolved_preserved")
            self.assertFalse(item["overwrite_authorized"])
            self.assertFalse(item["historical_size_hash_enforced"])

    def test_fails_closed_if_historical_unknown_set_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo, status, evidence_root, evidence = self.build_fixture(pathlib.Path(temporary))
            reconciliation = json.loads((evidence / "reconciliation.json").read_text(encoding="utf-8"))
            reconciliation["unknown_preserved"][0]["source_relative"] = "unexpected.json"
            (evidence / "reconciliation.json").write_text(json.dumps(reconciliation), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "reviewed four-artifact set"):
                MODULE.classify(repo_root=repo, status_root=status, evidence_root=evidence_root)

    def test_fails_closed_on_symlink_target_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo, status, evidence_root, _ = self.build_fixture(pathlib.Path(temporary))
            link = status / MODULE.COMPATIBILITY_LINK_RELATIVE
            link.unlink()
            link.symlink_to("network-sensor/index.html")
            with self.assertRaisesRegex(ValueError, "symlink target drift"):
                MODULE.classify(repo_root=repo, status_root=status, evidence_root=evidence_root)

    def test_tool_source_has_no_mutation_or_command_execution_surface(self):
        text = SCRIPT.read_text(encoding="utf-8")
        for forbidden in (
            "subprocess",
            "systemctl",
            "requests.",
            "urllib.request",
            ".write_text(",
            ".write_bytes(",
            ".unlink(",
            ".rename(",
            ".replace(",
            "os.chmod",
            "os.chown",
        ):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
