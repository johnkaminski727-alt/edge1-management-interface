import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "server"))
import cookie_monster_operator_view as operator_view
import cookie_monster_runtime as runtime


class RuntimeRegistryTests(unittest.TestCase):
    def test_default_registry_is_disabled_noncanonical_and_synthetic_detail_only(self):
        registry = runtime.load_registry(ROOT / "config" / "cookie_monster" / "datasets.json")
        row = registry["datasets"]["synthetic-media-v1"]
        self.assertFalse(row["enabled"])
        self.assertFalse(row["canonical_archive"])
        self.assertTrue(row["read_only_required"])
        self.assertTrue(row["operator_detail_publish"])
        with self.assertRaises(runtime.RuntimeErrorBoundary):
            runtime.resolve_dataset("synthetic-media-v1", registry)

    def test_runtime_rejects_unregistered_or_canonical_dataset(self):
        registry = {"datasets": {"bad": {"enabled": True, "canonical_archive": True, "read_only_required": True, "source_root": "/srv/cookie-monster/staging/bad"}}}
        with self.assertRaises(runtime.RuntimeErrorBoundary):
            runtime.resolve_dataset("missing", registry)
        with self.assertRaises(runtime.RuntimeErrorBoundary):
            runtime.resolve_dataset("bad", registry)

    def test_enabled_staging_dataset_resolves_only_inside_namespace(self):
        registry = {"datasets": {"ok": {"enabled": True, "canonical_archive": False, "read_only_required": True, "source_root": "/srv/cookie-monster/staging/ok"}}}
        self.assertEqual(str(runtime.resolve_dataset("ok", registry)), "/srv/cookie-monster/staging/ok")
        registry["datasets"]["ok"]["source_root"] = "/srv/canonical"
        with self.assertRaises(runtime.RuntimeErrorBoundary):
            runtime.resolve_dataset("ok", registry)


class OperatorViewTests(unittest.TestCase):
    def _status(self):
        return {
            "generated_at": "2026-08-22T00:00:00Z",
            "run_id": "run-1",
            "mode": "alpha-read-only",
            "source_kind": "staging",
            "job": {"dataset": "example"},
            "summary": {"files_discovered": 1},
            "tooling": {"ffprobe": {"available": True, "path": "/usr/bin/ffprobe"}},
            "fengus": {"connected": False},
            "assets": [{"source_asset_id": "sha256:" + "a" * 64, "source_asset_location": "private/name.mov", "filename": "name.mov", "metadata": {"GPS": "sensitive"}}],
            "knowledge_records": [{"knowledge_record_id": "kr-1", "source_asset_id": "sha256:" + "a" * 64, "source_asset_location": "private/name.mov", "facts": {"filename": "name.mov"}}],
            "duplicates": [],
            "review_queue": [],
        }

    def test_detail_defaults_closed_and_tool_paths_are_removed(self):
        registry = {"datasets": {"example": {"operator_detail_publish": False}}}
        view = operator_view.project_status(self._status(), registry)
        self.assertFalse(view["detail_published"])
        self.assertEqual(view["assets"], [])
        self.assertNotIn("path", view["tooling"]["ffprobe"])
        self.assertNotIn("GPS", json.dumps(view))
        self.assertNotIn("private/name.mov", json.dumps(view))

    def test_detail_requires_explicit_dataset_policy_but_raw_metadata_stays_out(self):
        registry = {"datasets": {"example": {"operator_detail_publish": True}}}
        view = operator_view.project_status(self._status(), registry)
        self.assertTrue(view["detail_published"])
        self.assertEqual(view["assets"][0]["filename"], "name.mov")
        self.assertNotIn("metadata", view["assets"][0])
        self.assertNotIn("GPS", json.dumps(view))


class PublisherTests(unittest.TestCase):
    def test_publisher_is_dry_run_by_default_and_bounded(self):
        text = (ROOT / "deploy" / "cookie-monster" / "publish.sh").read_text(encoding="utf-8")
        self.assertIn('case "$MODE"', text)
        self.assertIn("Use --apply", text)
        self.assertIn("wwcx-cookie-monster-", text)
        self.assertIn("rollback.sh", text)
        self.assertIn("operator-view", text)
        self.assertNotIn("knowledge-records.jsonl", text)
        self.assertNotIn("audit.jsonl", text)
        self.assertNotIn("review-decisions.jsonl", text)

    def test_dry_run_publishes_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            source = root / "repo" / "src" / "web" / "cookie-monster"
            (source / "assets").mkdir(parents=True)
            (source / "index.html").write_text("<html>cookie</html>\n", encoding="utf-8")
            (source / "assets" / "mascot.webp").write_bytes(b"mascot")
            view = root / "operator-view"
            view.mkdir()
            (view / "status.json").write_text(json.dumps({"mode": "alpha-read-only"}), encoding="utf-8")
            destination = root / "web"
            env = {"COOKIE_MONSTER_REPO_ROOT": str(root / "repo"), "COOKIE_MONSTER_OPERATOR_VIEW": str(view), "COOKIE_MONSTER_WEB_ROOT": str(destination)}
            completed = subprocess.run([str(ROOT / "deploy" / "cookie-monster" / "publish.sh")], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, env={**__import__("os").environ, **env})
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("preflight passed", completed.stdout)
            self.assertFalse(destination.exists())

    def test_dry_run_rejects_malformed_operator_json(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            source = root / "repo" / "src" / "web" / "cookie-monster"
            (source / "assets").mkdir(parents=True)
            (source / "index.html").write_text("<html>cookie</html>\n", encoding="utf-8")
            (source / "assets" / "mascot.webp").write_bytes(b"mascot")
            view = root / "operator-view"
            view.mkdir()
            (view / "acceptance.json").write_text("not-json\n", encoding="utf-8")
            env = {"COOKIE_MONSTER_REPO_ROOT": str(root / "repo"), "COOKIE_MONSTER_OPERATOR_VIEW": str(view), "COOKIE_MONSTER_WEB_ROOT": str(root / "web")}
            completed = subprocess.run([str(ROOT / "deploy" / "cookie-monster" / "publish.sh")], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, env={**__import__("os").environ, **env})
            self.assertNotEqual(completed.returncode, 0)


if __name__ == "__main__":
    unittest.main()
