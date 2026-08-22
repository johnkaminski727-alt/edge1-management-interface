import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "server"))
import cookie_monster_runtime as runtime


class RuntimeRegistryTests(unittest.TestCase):
    def test_default_registry_is_disabled_and_noncanonical(self):
        registry = runtime.load_registry(ROOT / "config" / "cookie_monster" / "datasets.json")
        row = registry["datasets"]["synthetic-media-v1"]
        self.assertFalse(row["enabled"])
        self.assertFalse(row["canonical_archive"])
        self.assertTrue(row["read_only_required"])
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


class PublisherTests(unittest.TestCase):
    def test_publisher_is_dry_run_by_default_and_bounded(self):
        text = (ROOT / "deploy" / "cookie-monster" / "publish.sh").read_text(encoding="utf-8")
        self.assertIn('case "$MODE"', text)
        self.assertIn("Use --apply", text)
        self.assertIn("wwcx-cookie-monster-", text)
        self.assertIn("rollback.sh", text)
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
            generated = root / "generated"
            generated.mkdir()
            (generated / "status.json").write_text(json.dumps({"mode": "alpha-read-only"}), encoding="utf-8")
            destination = root / "web"
            env = {
                "COOKIE_MONSTER_REPO_ROOT": str(root / "repo"),
                "COOKIE_MONSTER_GENERATED": str(generated),
                "COOKIE_MONSTER_WEB_ROOT": str(destination),
            }
            completed = subprocess.run(
                [str(ROOT / "deploy" / "cookie-monster" / "publish.sh")],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                env={**__import__("os").environ, **env},
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("preflight passed", completed.stdout)
            self.assertFalse(destination.exists())

    def test_dry_run_rejects_malformed_runtime_json(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            source = root / "repo" / "src" / "web" / "cookie-monster"
            (source / "assets").mkdir(parents=True)
            (source / "index.html").write_text("<html>cookie</html>\n", encoding="utf-8")
            (source / "assets" / "mascot.webp").write_bytes(b"mascot")
            generated = root / "generated"
            generated.mkdir()
            (generated / "acceptance.json").write_text("not-json\n", encoding="utf-8")
            env = {
                "COOKIE_MONSTER_REPO_ROOT": str(root / "repo"),
                "COOKIE_MONSTER_GENERATED": str(generated),
                "COOKIE_MONSTER_WEB_ROOT": str(root / "web"),
            }
            completed = subprocess.run(
                [str(ROOT / "deploy" / "cookie-monster" / "publish.sh")],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                env={**__import__("os").environ, **env},
            )
            self.assertNotEqual(completed.returncode, 0)


if __name__ == "__main__":
    unittest.main()
