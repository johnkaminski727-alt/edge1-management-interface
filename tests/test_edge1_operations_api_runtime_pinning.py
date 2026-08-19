import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[1]
SCRIPT = ROOT / "deploy" / "pin-edge1-operations-api-runtime.sh"


class OperationsApiRuntimePinningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SCRIPT.read_text(encoding="utf-8")

    def test_runtime_is_restricted_to_dedicated_tree(self):
        self.assertIn("/opt/edge1-operations-api-runtimes/*", self.text)
        self.assertIn("runtime worktree is not clean", self.text)
        self.assertIn("git -C \"$RUNTIME\" rev-parse HEAD", self.text)

    def test_dropin_replaces_absolute_execstart_and_root(self):
        self.assertIn("ExecStart=\n", self.text)
        self.assertIn("ExecStart=/usr/bin/python3 $RUNTIME/server/edge1_operations_api.py", self.text)
        self.assertIn("WorkingDirectory=$RUNTIME", self.text)
        self.assertIn("Environment=EDGE1_OPS_ROOT=$RUNTIME", self.text)
        self.assertIn("ReadOnlyPaths=$RUNTIME", self.text)

    def test_readiness_is_bounded_and_rollback_is_automatic(self):
        self.assertIn('while [ "$i" -le 20 ]', self.text)
        self.assertIn("curl -fsS --max-time 2 http://127.0.0.1:8097/healthz", self.text)
        self.assertIn('"$EVID/rollback.sh"', self.text)
        self.assertIn("journal.failed.txt", self.text)

    def test_security_contract_remains_read_only_and_loopback(self):
        self.assertIn('data.get("mutations_enabled") is not False', self.text)
        self.assertIn("NoNewPrivileges", self.text)
        self.assertIn("127.0.0.1:8097", self.text)
        self.assertIn("0\\.0\\.0\\.0:8097", self.text)
        forbidden = (
            "EDGE1_OPS_MUTATIONS_ENABLED=true",
            "chmod 777",
            "usermod",
            "sudoers",
            "iptables",
            "nft add",
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, self.text)


if __name__ == "__main__":
    unittest.main()
