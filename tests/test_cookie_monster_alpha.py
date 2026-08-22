import hashlib
import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "server"))
import cookie_monster_alpha as cm


class CookieMonsterAlphaTests(unittest.TestCase):
    def _make_source(self, root: pathlib.Path) -> pathlib.Path:
        source = root / "staging-source"
        source.mkdir()
        (source / "alpha.txt").write_text("cookie alpha\n", encoding="utf-8")
        (source / "duplicate.txt").write_text("cookie alpha\n", encoding="utf-8")
        (source / "different.bin").write_bytes(b"\x00\x01\x02\x03")
        return source

    def test_rejects_output_inside_source(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            source = self._make_source(root)
            with self.assertRaises(cm.AlphaBoundaryError):
                cm.validate_paths(source, source / "generated")

    def test_ingest_is_read_only_and_detects_duplicates(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            source = self._make_source(root)
            before = {p.relative_to(source): (p.read_bytes(), p.stat().st_mtime_ns) for p in source.rglob("*") if p.is_file()}
            with mock.patch.object(cm, "extract_metadata", return_value=({}, [])):
                snapshot = cm.build_snapshot(source)
            after = {p.relative_to(source): (p.read_bytes(), p.stat().st_mtime_ns) for p in source.rglob("*") if p.is_file()}
            self.assertEqual(before, after)
            self.assertEqual(snapshot["summary"]["files_discovered"], 3)
            self.assertEqual(snapshot["summary"]["unique_assets"], 2)
            self.assertEqual(snapshot["summary"]["duplicate_groups"], 1)
            self.assertEqual(snapshot["duplicates"][0]["count"], 2)
            self.assertEqual(snapshot["summary"]["unauthorized_source_writes"], 0)

    def test_source_asset_id_is_content_addressed_sha256(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            source = self._make_source(root)
            expected = hashlib.sha256((source / "alpha.txt").read_bytes()).hexdigest()
            with mock.patch.object(cm, "extract_metadata", return_value=({}, [])):
                snapshot = cm.build_snapshot(source)
            alpha = next(row for row in snapshot["assets"] if row["filename"] == "alpha.txt")
            self.assertEqual(alpha["source_asset_id"], f"sha256:{expected}")

    def test_knowledge_records_are_hash_chained_and_provenanced(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            source = self._make_source(root)
            with mock.patch.object(cm, "extract_metadata", return_value=({}, [])):
                snapshot = cm.build_snapshot(source, actor="test-actor", actor_version="test-v1")
            records = snapshot["knowledge_records"]
            self.assertTrue(records)
            self.assertIsNone(records[0]["previous_record_hash"])
            for index, record in enumerate(records):
                self.assertTrue(record["source_asset_id"].startswith("sha256:"))
                self.assertEqual(record["ingestion_actor"], "test-actor")
                self.assertEqual(record["extraction_method_version"], "test-v1")
                self.assertTrue(record["record_hash"].startswith("sha256:"))
                self.assertTrue(record["idempotency_key"].startswith("sha256:"))
                if index:
                    self.assertEqual(record["previous_record_hash"], records[index - 1]["record_hash"])

    def test_metadata_failure_becomes_review_item_not_pipeline_failure(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            source = self._make_source(root)
            diagnostic = [{"tool": "ffprobe", "error": "synthetic failure"}]
            with mock.patch.object(cm, "extract_metadata", return_value=({}, diagnostic)):
                snapshot = cm.build_snapshot(source)
            self.assertEqual(snapshot["summary"]["review_items"], 3)
            self.assertTrue(all(r["review_status"] == "pending_review" for r in snapshot["knowledge_records"]))
            self.assertTrue(any(e["event"] == "metadata.diagnostic" for e in snapshot["audit"]))

    def test_write_snapshot_outputs_status_audit_and_append_only_record_format(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            source = self._make_source(root)
            output = root / "generated"
            with mock.patch.object(cm, "extract_metadata", return_value=({}, [])):
                snapshot = cm.build_snapshot(source)
            cm.write_snapshot(snapshot, output)
            loaded = json.loads((output / "status.json").read_text(encoding="utf-8"))
            self.assertEqual(loaded["schema"], cm.SCHEMA_VERSION)
            records = cm.read_jsonl(output / "knowledge-records.jsonl")
            audit = cm.read_jsonl(output / "audit.jsonl")
            self.assertEqual(len(records), 3)
            self.assertGreaterEqual(len(audit), 3)

    def test_repeat_run_is_idempotent_and_preserves_prior_audit(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            source = self._make_source(root)
            output = root / "generated"
            with mock.patch.object(cm, "extract_metadata", return_value=({}, [])):
                first = cm.build_snapshot(source)
                cm.write_snapshot(first, output)
                first_records = (output / "knowledge-records.jsonl").read_text(encoding="utf-8")
                first_audit = (output / "audit.jsonl").read_text(encoding="utf-8")
                existing = cm.read_jsonl(output / "knowledge-records.jsonl")
                second = cm.build_snapshot(source, existing_records=existing)
                cm.write_snapshot(second, output)
            self.assertEqual((output / "knowledge-records.jsonl").read_text(encoding="utf-8"), first_records)
            second_audit = (output / "audit.jsonl").read_text(encoding="utf-8")
            self.assertTrue(second_audit.startswith(first_audit))
            self.assertGreater(len(second_audit), len(first_audit))
            self.assertEqual(second["summary"]["new_knowledge_records"], 0)
            self.assertEqual(second["summary"]["reused_knowledge_records"], 3)
            self.assertEqual(
                [r["knowledge_record_id"] for r in second["knowledge_records"]],
                [r["knowledge_record_id"] for r in existing],
            )
            self.assertTrue(any(e["event"] == "knowledge_record.reused" for e in second["audit"]))

    def test_legacy_record_without_idempotency_key_is_reused(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            source = self._make_source(root)
            with mock.patch.object(cm, "extract_metadata", return_value=({}, [])):
                first = cm.build_snapshot(source)
            legacy = [dict(row) for row in first["knowledge_records"]]
            for row in legacy:
                row.pop("idempotency_key", None)
            with mock.patch.object(cm, "extract_metadata", return_value=({}, [])):
                second = cm.build_snapshot(source, existing_records=legacy)
            self.assertEqual(second["summary"]["new_knowledge_records"], 0)
            self.assertEqual([r["knowledge_record_id"] for r in second["knowledge_records"]], [r["knowledge_record_id"] for r in legacy])

    def test_symlink_directory_escape_fails_closed(self):
        if not hasattr(os, "symlink"):
            self.skipTest("symlink unsupported")
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            source = self._make_source(root)
            outside = root / "outside"
            outside.mkdir()
            (outside / "secret.txt").write_text("outside\n", encoding="utf-8")
            link = source / "escape"
            try:
                os.symlink(outside, link, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink unavailable: {exc}")
            with self.assertRaises(cm.AlphaBoundaryError):
                cm.discover_files(source)

    def test_metadata_budget_stops_tool_chain(self):
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / "asset.bin"
            path.write_bytes(b"x")
            with mock.patch.object(cm, "_tool_path", return_value="/fake/tool"), mock.patch.object(cm, "_run_json") as run_json:
                metadata, diagnostics = cm.extract_metadata(path, budget_seconds=0)
            self.assertEqual(metadata, {})
            run_json.assert_not_called()
            self.assertEqual(diagnostics[0]["tool"], "budget")

    def test_run_budget_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            source = self._make_source(root)
            with self.assertRaises(cm.AlphaBoundaryError):
                cm.build_snapshot(source, run_time_budget_seconds=0)


if __name__ == "__main__":
    unittest.main()
