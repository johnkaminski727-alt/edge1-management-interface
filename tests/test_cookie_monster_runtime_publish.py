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
        (repo / "src/web/cookie-monster/assets/mascot.webp").write_bytes(b"webp")
        generated.mkdir()
        (generated / "status.json").write_text(json.dumps({"schema": cm.STATUS_SCHEMA, "run_id": "run-test"}), encoding="utf-8")
        return repo, generated, web, backups

    def test_preflight_is_read_only(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            repo, generated, web, backups = self.make_layout(root)
            plan = cm.preflight(repo, generated, web, backups)
            self.assertFalse(web.exists())
            self.assertEqual(plan["runtime_presence"]["status.json"], True)
            self.assertEqual(plan["runtime_presence"]["acceptance.json"], False)

    def test_apply_publishes_and_removes_stale_optional_state(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            repo, generated, web, backups = self.make_layout(root)
            web.mkdir()
            (web / "acceptance.json").write_text('{"stale":true}\n', encoding="utf-8")
            (generated / "review-state.json").write_text('{"schema":"review"}\n', encoding="utf-8")
            plan = cm.preflight(repo, generated, web, backups)
            backup, manifest = cm.apply(plan)
            self.assertTrue((web / "index.html").is_file())
            self.assertTrue((web / "assets/mascot.webp").is_file())
            self.assertTrue((web / "status.json").is_file())
            self.assertTrue((web / "review-state.json").is_file())
            self.assertFalse((web / "acceptance.json").exists())
            self.assertEqual(manifest["schema"], cm.MANIFEST_SCHEMA)
            self.assertTrue((backup / "acceptance.json").is_file())

    def test_malformed_optional_snapshot_fails_before_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            repo, generated, web, backups = self.make_layout(root)
            (generated / "job-status.json").write_text("not-json", encoding="utf-8")
            with self.assertRaises(cm.PublishError):
                cm.preflight(repo, generated, web, backups)
            self.assertFalse(web.exists())

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
