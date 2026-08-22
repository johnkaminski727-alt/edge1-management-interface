import pathlib
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "server"))
import cookie_monster_acceptance as acceptance
import cookie_monster_alpha as alpha


class CookieMonsterAcceptanceTests(unittest.TestCase):
    def test_m6_synthetic_acceptance_passes_end_to_end(self):
        with tempfile.TemporaryDirectory() as td, mock.patch.object(alpha, "extract_metadata", return_value=({}, [])):
            report = acceptance.run_acceptance(pathlib.Path(td))
            self.assertEqual(report["result"], "pass")
            self.assertEqual(report["summary"]["assets"], 5)
            self.assertEqual(report["summary"]["provenance_gaps"], 0)
            self.assertEqual(report["summary"]["unauthorized_source_writes"], 0)
            self.assertEqual(report["summary"]["fengus_jobs_outside_allowlist"], 0)
            self.assertTrue(all(item["pass"] for item in report["criteria"].values()))
            self.assertTrue((pathlib.Path(td) / "generated" / "acceptance.json").is_file())
            self.assertTrue((pathlib.Path(td) / "generated" / "review-state.json").is_file())
            self.assertTrue((pathlib.Path(td) / "generated" / "job-status.json").is_file())

    def test_synthetic_source_refuses_to_overwrite_nonempty_directory(self):
        with tempfile.TemporaryDirectory() as td:
            source = pathlib.Path(td) / "synthetic-staging"
            source.mkdir()
            (source / "existing.txt").write_text("preserve me", encoding="utf-8")
            with self.assertRaises(acceptance.AcceptanceError):
                acceptance.prepare_synthetic_source(source)
            self.assertEqual((source / "existing.txt").read_text(encoding="utf-8"), "preserve me")

    def test_provenance_verifier_detects_wrong_source_hash(self):
        with tempfile.TemporaryDirectory() as td:
            source = pathlib.Path(td)
            (source / "asset.txt").write_text("real bytes", encoding="utf-8")
            records = [{"knowledge_record_id": "kr-" + "a" * 32, "source_asset_location": "asset.txt", "source_asset_id": "sha256:" + "0" * 64}]
            self.assertEqual(len(acceptance.verify_provenance(records, source)), 1)

    def test_review_chain_verifier_detects_tampering(self):
        record = {
            "knowledge_record_id": "kr-" + "a" * 32,
            "source_asset_id": "sha256:" + "b" * 64,
            "source_asset_location": "asset.txt",
            "review_status": "pending_review",
        }
        import cookie_monster_review as review
        event = review.make_decision(
            [record],
            [],
            record["knowledge_record_id"],
            "approved",
            "operator",
            "verified",
            timestamp="2026-08-22T08:00:00Z",
        )
        self.assertEqual(acceptance.verify_review_chain([event]), [])
        event["reason"] = "tampered"
        self.assertEqual(len(acceptance.verify_review_chain([event])), 1)

    def test_ui_surfaces_m6_acceptance_evidence(self):
        text = (ROOT / "src" / "web" / "cookie-monster" / "index.html").read_text(encoding="utf-8")
        self.assertIn("M6 acceptance", text)
        self.assertIn("acceptance.json", text)


if __name__ == "__main__":
    unittest.main()
