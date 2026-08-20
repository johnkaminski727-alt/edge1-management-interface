#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/security/classify-edge1-security-boundary-evidence.py"
SPEC = importlib.util.spec_from_file_location("edge1_security_boundary_classifier", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

NAMES = sorted(MODULE.REVIEWED_UNKNOWN_NAMES)


def digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SecurityBoundaryEvidenceClassifierTests(unittest.TestCase):
    def build_fixture(self, root: pathlib.Path):
        repo = root / "repo"
        status = root / "status"
        evidence_root = root / "evidence"
        evidence = evidence_root / "20260820T010000Z"
        manifest_path = repo / "config/security/edge1-restricted-artifact-migration-manifest.json"
        manifest_path.parent.mkdir(parents=True)
        status.mkdir()
        evidence.mkdir(parents=True)

        exact = []
        inventory = []
        unknowns = []
        for index, name in enumerate(NAMES):
            source_rel = f"sources/{index}.py"
            source = repo / source_rel
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text(f"# provenance for {name}\n", encoding="utf-8")
            live = status / name
            live.write_bytes((name + "\n").encode("utf-8"))
            mode = "0644"
            os.chmod(live, 0o644)
            record = {
                "source_relative": name,
                "sha256": digest(live),
                "mode": mode,
                "bytes": live.stat().st_size,
                "action": "preserve_review",
                "reason": "not_in_repository_declared_manifest",
            }
            unknowns.append(record)
            inventory.append(
                {
                    "path": str(live),
                    "sha256": record["sha256"],
                    "mode": mode,
                    "bytes": record["bytes"],
                }
            )
            exact.append(
                {
                    "source_relative": name,
                    "target_relative": f"data/{name}",
                    "classification": "restricted_operations_data",
                    "required_scopes": ["edge1.status.detail.read"],
                    "repository_source": source_rel,
                }
            )

        target = status / MODULE.COMPATIBILITY_TARGET_RELATIVE
        target.parent.mkdir(parents=True)
        target.write_text('{"read_only": true}\n', encoding="utf-8")
        os.chmod(target, 0o644)
        inventory.append(
            {
                "path": str(target.resolve()),
                "sha256": digest(target),
                "mode": "0644",
                "bytes": target.stat().st_size,
            }
        )
        link = status / MODULE.COMPATIBILITY_LINK_RELATIVE
        link.symlink_to(MODULE.COMPATIBILITY_TARGET_RELATIVE)

        manifest_path.write_text(
            json.dumps({"known_exact_artifacts": exact}), encoding="utf-8"
        )
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
        (evidence / "public-filesystem-inventory.json").write_text(
            json.dumps(inventory), encoding="utf-8"
        )
        (evidence / "public-filesystem-anomalies.json").write_text(
            json.dumps([{"path": str(link), "type": "symlink"}]), encoding="utf-8"
        )
        return repo, status, evidence_root, evidence

    def test_classifies_exact_four_and_contained_compatibility_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo, status, evidence_root, evidence = self.build_fixture(
                pathlib.Path(temporary)
            )
            value = MODULE.classify(
                repo_root=repo,
                status_root=status,
                evidence_root=evidence_root,
            )
            self.assertEqual(value["selected_evidence_dir"], str(evidence))
            self.assertEqual(value["classified_unknown_count"], 4)
            self.assertEqual(value["classified_filesystem_anomaly_count"], 1)
            self.assertTrue(
                value["classified_filesystem_anomaly"][
                    "contained_within_status_root"
                ]
            )
            self.assertFalse(value["file_contents_printed"])
            self.assertFalse(value["live_files_mutated"])
            self.assertFalse(value["staging_authorized"])
            self.assertFalse(value["cutover_authorized"])

    def test_fails_closed_on_live_hash_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo, status, evidence_root, _ = self.build_fixture(pathlib.Path(temporary))
            (status / NAMES[0]).write_text("changed\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA-256 drift|byte-count drift"):
                MODULE.classify(
                    repo_root=repo,
                    status_root=status,
                    evidence_root=evidence_root,
                )

    def test_fails_closed_on_symlink_target_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo, status, evidence_root, _ = self.build_fixture(pathlib.Path(temporary))
            link = status / MODULE.COMPATIBILITY_LINK_RELATIVE
            link.unlink()
            link.symlink_to(NAMES[0])
            with self.assertRaisesRegex(ValueError, "symlink target drift"):
                MODULE.classify(
                    repo_root=repo,
                    status_root=status,
                    evidence_root=evidence_root,
                )

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
