from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AvaPhase3OPreflightTests(unittest.TestCase):
    def setUp(self):
        self.script = (ROOT / "deploy" / "preflight-ava-phase3o-release.sh").read_text(encoding="utf-8")

    def test_requires_exact_detached_clean_release(self):
        self.assertIn("--expected-commit=SHA is required", self.script)
        self.assertIn("expected commit mismatch", self.script)
        self.assertIn("release worktree is not clean", self.script)
        self.assertIn("preflight requires a detached exact-commit worktree", self.script)
        self.assertIn('git -c safe.directory="$REPO_ROOT"', self.script)

    def test_is_read_only(self):
        forbidden = (
            "systemctl restart",
            "systemctl start",
            "systemctl enable",
            "systemctl disable",
            "mv -Tf",
            "ln -sfn",
            "install -m",
            "rm -rf",
            "git reset",
            "git checkout",
            "git pull",
            "git clean",
        )
        for token in forbidden:
            self.assertNotIn(token, self.script)

    def test_runs_dry_runs_and_focused_tests(self):
        self.assertIn("install-bigbird-private-library-runtime.sh\" --dry-run", self.script)
        self.assertIn("install-ava-readonly-gateway.sh\" --dry-run", self.script)
        self.assertIn("install-ava-browser-worker.sh\" --dry-run", self.script)
        self.assertIn("tests.test_ava_phase3o_commissioning", self.script)
        self.assertIn("No files, services, runtime pointers, credentials, routes, or browser state were changed.", self.script)


if __name__ == "__main__":
    unittest.main()
