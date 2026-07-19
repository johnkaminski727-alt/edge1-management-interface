import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "server" / "edge1_operations_api.py"


class OperationsApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.repo = root / "repo"
        self.repo.mkdir()
        self.allowlist = root / "allowlist.json"
        self.secret = root / "secret"
        self.db = root / "audit.sqlite3"
        self.secret.write_text("x" * 64, encoding="utf-8")
        self.allowlist.write_text(json.dumps({"actions": {
            "safe": {"argv": ["/usr/bin/printf", "ok"], "mutating": False},
            "write": {"argv": ["/usr/bin/printf", "no"], "mutating": True}
        }}), encoding="utf-8")
        os.environ.update({
            "EDGE1_OPS_ROOT": str(self.repo),
            "EDGE1_OPS_ALLOWLIST": str(self.allowlist),
            "EDGE1_OPS_SECRET_FILE": str(self.secret),
            "EDGE1_OPS_DB": str(self.db),
            "EDGE1_OPS_MUTATIONS_ENABLED": "false",
        })
        spec = importlib.util.spec_from_file_location("edge1_ops_test", MODULE_PATH)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def tearDown(self):
        self.tmp.cleanup()

    def test_safe_action_runs_and_audits(self):
        result = self.module.run_action("safe", "tester", "hash")
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["stdout"], "ok")
        with self.module.connect_db() as conn:
            self.assertEqual(conn.execute("select count(*) from operation_audit").fetchone()[0], 1)

    def test_mutation_is_disabled_by_default(self):
        with self.assertRaises(PermissionError):
            self.module.safe_action("write")

    def test_unknown_action_is_rejected(self):
        with self.assertRaises(KeyError):
            self.module.safe_action("shell")

    def test_cwd_escape_is_rejected(self):
        self.allowlist.write_text(json.dumps({"actions": {
            "escape": {"argv": ["/usr/bin/true"], "cwd": "/tmp"}
        }}), encoding="utf-8")
        with self.assertRaises(ValueError):
            self.module.safe_action("escape")


if __name__ == "__main__":
    unittest.main()
