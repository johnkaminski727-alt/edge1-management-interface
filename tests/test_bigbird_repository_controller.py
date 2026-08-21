#!/usr/bin/env python3

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/bigbird_repository_controller.py"
SPEC = importlib.util.spec_from_file_location("bigbird_repository_controller", MODULE_PATH)
CONTROL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTROL)


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(repo), *args], text=True, capture_output=True, check=True)
    return proc.stdout.strip()


class BigBirdRepositoryControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.repo = root / "repo"
        self.state = root / "state"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.name", "Test User")
        git(self.repo, "config", "user.email", "test@example.invalid")
        (self.repo / "docs").mkdir()
        (self.repo / "server").mkdir()
        (self.repo / "docs/example.md").write_text("original\n", encoding="utf-8")
        (self.repo / "server/example.py").write_text("value = 1\n", encoding="utf-8")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "initial")
        self.base = git(self.repo, "rev-parse", "HEAD")
        CONTROL.REPO = self.repo.resolve()
        CONTROL.STATE_ROOT = self.state.resolve()

    def tearDown(self):
        self.tmp.cleanup()

    def request(self, **updates):
        value = {
            "request_id": "req-001",
            "expected_base_sha": self.base,
            "branch": "agent/bigbird-test-001",
            "commit_message": "Update example documentation",
            "changes": [
                {"path": "docs/example.md", "content": "candidate\n", "mode": "replace"},
            ],
        }
        value.update(updates)
        return value

    def test_commit_creates_agent_branch_without_touching_running_checkout(self):
        result = CONTROL.create_branch_commit(self.request())
        self.assertEqual(result["status"], "committed")
        self.assertFalse(result["pushed"])
        self.assertFalse(result["deployed"])
        self.assertEqual((self.repo / "docs/example.md").read_text(encoding="utf-8"), "original\n")
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), self.base)
        branch_commit = git(self.repo, "rev-parse", "refs/heads/agent/bigbird-test-001")
        self.assertEqual(branch_commit, result["commit_sha"])
        self.assertEqual(git(self.repo, "rev-parse", branch_commit + "^"), self.base)
        content = git(self.repo, "show", branch_commit + ":docs/example.md")
        self.assertEqual(content, "candidate")

    def test_idempotent_replay_returns_existing_commit(self):
        first = CONTROL.create_branch_commit(self.request())
        second = CONTROL.create_branch_commit(self.request())
        self.assertEqual(first["commit_sha"], second["commit_sha"])
        self.assertTrue(second["idempotent_replay"])

    def test_request_id_reuse_with_different_content_is_rejected(self):
        CONTROL.create_branch_commit(self.request())
        changed = self.request(changes=[{"path": "docs/example.md", "content": "different\n", "mode": "replace"}])
        with self.assertRaisesRegex(CONTROL.RepositoryWriteError, "different content"):
            CONTROL.create_branch_commit(changed)

    def test_main_branch_is_rejected(self):
        with self.assertRaisesRegex(CONTROL.RepositoryWriteError, "agent/bigbird"):
            CONTROL.create_branch_commit(self.request(branch="main"))

    def test_sensitive_config_path_is_rejected(self):
        bad = self.request(changes=[{
            "path": "config/edge1-operations-allowlist.json",
            "content": "{}\n",
            "mode": "replace",
        }])
        with self.assertRaisesRegex(CONTROL.RepositoryWriteError, "approved repository prefixes"):
            CONTROL.create_branch_commit(bad)

    def test_replace_requires_existing_target(self):
        bad = self.request(changes=[{"path": "docs/missing.md", "content": "new\n", "mode": "replace"}])
        with self.assertRaisesRegex(CONTROL.RepositoryWriteError, "replace target does not exist"):
            CONTROL.create_branch_commit(bad)
        proc = subprocess.run(
            ["git", "-C", str(self.repo), "show-ref", "--verify", "--quiet", "refs/heads/agent/bigbird-test-001"]
        )
        self.assertNotEqual(proc.returncode, 0)

    def test_invalid_python_candidate_is_rejected_before_branch_creation(self):
        bad = self.request(changes=[{
            "path": "server/example.py",
            "content": "def broken(:\n    pass\n",
            "mode": "replace",
        }])
        with self.assertRaisesRegex(CONTROL.RepositoryWriteError, "python syntax validation failed"):
            CONTROL.create_branch_commit(bad)
        proc = subprocess.run(
            ["git", "-C", str(self.repo), "show-ref", "--verify", "--quiet", "refs/heads/agent/bigbird-test-001"]
        )
        self.assertNotEqual(proc.returncode, 0)

    def test_secret_material_is_rejected(self):
        bad = self.request(changes=[{
            "path": "docs/example.md",
            "content": "-----BEGIN PRIVATE KEY-----\nabc\n",
            "mode": "replace",
        }])
        with self.assertRaisesRegex(CONTROL.RepositoryWriteError, "credential material"):
            CONTROL.create_branch_commit(bad)


if __name__ == "__main__":
    unittest.main()
