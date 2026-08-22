import importlib.util
import json
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).parents[1]
MODULE_PATH = ROOT / "deploy" / "cookie_monster_runtime_publish.py"
spec = importlib.util.spec_from_file_location("cm_publish", MODULE_PATH)
cm = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(cm)


class RuntimePublishTests(unittest.TestCase):
    def make_layout(self, root: pathlib.Path):
        repo = root / "repo"
        generated = root / "generated"
        web = root / "web"
        backups = root / "backups"
        (repo / "src/web/cookie-monster/assets").mkdir(parents=True)
        (repo / "src/web/cookie-monster/index.html").write_text("<html>cm</html>\n", encoding="utf-8")
        (repo / "src/web/cookie-monster/assets" / "mascot.webp").write_bytes(b"webp")
        generated.mkdir()
        status = {
            "schema": cm.STATUS_SCHEMA,
            "generated_at": "2026-08-22T00:00:00Z",
            "run_id": "run-test",
            "mode": "alpha-read-only",
            "source_kind": "staging",
            "summary": {
                "files_discovered": 1,
                "unique_assets": 1,
                "duplicate_groups": 0,
                "knowledge_records": 1,
                "review_items": 1,
                "unauthorized_source_writes": 0,
            },
            "tooling": {"ffprobe": {"available": True, "path": "/usr/bin/ffprobe"}},
            "fengus": {"connected": False, "mode": "bounded", "jobs_active": 0, "internal_path": "/srv/archive"},
            "assets": [
                {
                    "source_asset_id": "sha256:" + "a" * 64,
                    "source_asset_location": "private/name.mov",
                    "filename": "name.mov",
                    "extension": ".mov",
                    "size_bytes": 123,
                    "mime_type": "video/quicktime",
                    "metadata": {"GPS": "sensitive"},
                }
            ],
            "duplicates": [],
            "knowledge_records": [
                {
                    "knowledge_record_id": "kr-1",
                    "source_asset_id": "sha256:" + "a" * 64,
                    "source_asset_location": "private/name.mov",
                    "confidence": 1.0,
                    "review_status": "draft",
                    "record_hash": "sha256:" + "b" * 64,
                    "previous_record_hash": None,
                    "extraction_method": "alpha",
                    "extraction_method_version": "1",
                    "facts": {"filename": "name.mov", "size_bytes": 123, "secret_note": "do-not-publish"},
                }
            ],
            "review_queue": [
                {
                    "knowledge_record_id": "kr-1",
                    "source_asset_id": "sha256:" + "a" * 64,
                    "source_asset_location": "private/name.mov",
                    "review_status": "draft",
                    "reason": "initial_alpha_record",
                }
            ],
        }
        (generated / "status.json").write_text(json.dumps(status), encoding="utf-8")
        return repo, generated, web, backups

    def test_preflight_is_read_only(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            repo, generated, web, backups = self.make_layout(root)
            plan = cm.preflight(repo, generated, web, backups)
            self.assertFalse(web.exists())
            self.assertEqual(plan["runtime_presence"]["status.json"], True)
            self.assertEqual(plan["runtime_presence"]["acceptance.json"], False)
            self.assertFalse(plan["detail_published"])

    def test_apply_publishes_and_removes_stale_optional_state(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            repo, generated, web, backups = self.make_layout(root)
            web.mkdir()
            (web / "acceptance.json").write_text('{"stale":true}\n', encoding="utf-8")
            (generated / "review-state.json").write_text(
                json.dumps({"schema": "review", "summary": {"draft": 1}, "records": []}),
                encoding="utf-8",
            )
            plan = cm.preflight(repo, generated, web, backups)
            backup, manifest = cm.apply(plan)
            self.assertTrue((web / "index.html").is_file())
            self.assertTrue((web / "assets/mascot.webp").is_file())
            self.assertTrue((web / "status.json").is_file())
            self.assertTrue((web / "review-state.json").is_file())
            self.assertFalse((web / "acceptance.json").exists())
            self.assertEqual(json.loads((web / "status.json").read_text())["schema"], cm.OPERATOR_VIEW_SCHEMA)
            self.assertEqual(manifest["schema"], cm.MANIFEST_SCHEMA)
            self.assertFalse(manifest["detail_published"])
            self.assertTrue((backup / "acceptance.json").is_file())

    def test_default_publication_minimizes_runtime_details(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            repo, generated, web, backups = self.make_layout(root)
            (generated / "review-state.json").write_text(
                json.dumps(
                    {
                        "summary": {"draft": 1},
                        "records": [
                            {
                                "knowledge_record_id": "kr-1",
                                "source_asset_id": "sha256:" + "a" * 64,
                                "source_asset_location": "private/name.mov",
                                "review_status": "draft",
                                "allowed_next": ["pending_review"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            plan = cm.preflight(repo, generated, web, backups)
            _, manifest = cm.apply(plan)
            published = "\n".join(
                path.read_text(encoding="utf-8")
                for path in web.glob("*.json")
                if path.is_file()
            )
            status = json.loads((web / "status.json").read_text(encoding="utf-8"))
            review = json.loads((web / "review-state.json").read_text(encoding="utf-8"))
            self.assertEqual(status["assets"], [])
            self.assertEqual(status["knowledge_records"], [])
            self.assertNotIn("source_asset_location", review["records"][0])
            self.assertNotIn("/usr/bin/ffprobe", published)
            self.assertNotIn("private/name.mov", published)
            self.assertNotIn("GPS", published)
            self.assertNotIn("do-not-publish", published)
            self.assertNotIn("generated_root", manifest)
            self.assertNotIn(str(generated), json.dumps(manifest))

    def test_explicit_detail_still_excludes_raw_metadata_and_tool_paths(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            repo, generated, web, backups = self.make_layout(root)
            plan = cm.preflight(repo, generated, web, backups, publish_detail=True)
            _, manifest = cm.apply(plan)
            status = json.loads((web / "status.json").read_text(encoding="utf-8"))
            published = json.dumps(status)
            self.assertTrue(status["detail_published"])
            self.assertEqual(status["assets"][0]["filename"], "name.mov")
            self.assertEqual(status["assets"][0]["source_asset_location"], "private/name.mov")
            self.assertNotIn("metadata", status["assets"][0])
            self.assertNotIn("GPS", published)
            self.assertNotIn("/usr/bin/ffprobe", published)
            self.assertNotIn("secret_note", published)
            self.assertTrue(manifest["detail_published"])

    def test_detail_publication_requires_safe_staging_status(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            repo, generated, web, backups = self.make_layout(root)
            status_path = generated / "status.json"
            status = json.loads(status_path.read_text(encoding="utf-8"))
            status["source_kind"] = "canonical"
            status_path.write_text(json.dumps(status), encoding="utf-8")
            with self.assertRaises(cm.PublishError):
                cm.preflight(repo, generated, web, backups, publish_detail=True)
            status["source_kind"] = "staging"
            status["summary"]["unauthorized_source_writes"] = 1
            status_path.write_text(json.dumps(status), encoding="utf-8")
            with self.assertRaises(cm.PublishError):
                cm.preflight(repo, generated, web, backups, publish_detail=True)

    def test_malformed_optional_snapshot_fails_before_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            repo, generated, web, backups = self.make_layout(root)
            (generated / "job-status.json").write_text("not-json", encoding="utf-8")
            with self.assertRaises(cm.PublishError):
                cm.preflight(repo, generated, web, backups)
            self.assertFalse(web.exists())

    def test_symlink_runtime_snapshot_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            repo, generated, web, backups = self.make_layout(root)
            target = root / "review-target.json"
            target.write_text('{"summary":{}}\n', encoding="utf-8")
            (generated / "review-state.json").symlink_to(target)
            with self.assertRaises(cm.PublishError):
                cm.preflight(repo, generated, web, backups)

    def test_rollback_restores_exact_managed_state(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            repo, generated, web, backups = self.make_layout(root)
            web.mkdir()
            original = b"old-index\n"
            (web / "index.html").write_bytes(original)
            (web / "acceptance.json").write_text('{"old":1}\n', encoding="utf-8")
            plan = cm.preflight(repo, generated, web, backups)
            backup, _ = cm.apply(plan)
            self.assertNotEqual((web / "index.html").read_bytes(), original)
            self.assertFalse((web / "acceptance.json").exists())
            cm.rollback(backup, web)
            self.assertEqual((web / "index.html").read_bytes(), original)
            self.assertEqual(json.loads((web / "acceptance.json").read_text()), {"old": 1})
            self.assertFalse((web / "runtime-manifest.json").exists())

    def test_rejects_runtime_paths_inside_repository(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            repo, generated, web, backups = self.make_layout(root)
            with self.assertRaises(cm.PublishError):
                cm.validate_layout(repo, generated, repo / "src/web/cookie-monster/runtime", backups)

    def test_wrong_status_schema_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            repo, generated, web, backups = self.make_layout(root)
            (generated / "status.json").write_text('{"schema":"wrong"}\n', encoding="utf-8")
            with self.assertRaises(cm.PublishError):
                cm.preflight(repo, generated, web, backups)


if __name__ == "__main__":
    unittest.main()
